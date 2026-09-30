import { computed, onBeforeUnmount, reactive, ref, shallowRef } from 'vue'
import { ElMessage } from 'element-plus'
import {
  openSpeechStream,
  type SpeechEvent,
  type SpeechStreamConnection
} from '@/api/speechStream'
import {
  CHUNK_DURATION_MS,
  DOWNLINK_SAMPLE_RATE,
  computeLevel,
  downsampleTo16k,
  floatToInt16Bytes,
  int16BytesToFloat32
} from '@/utils/pcm'

/**
 * 语音面试的状态机（T7.7）。
 *
 * 一轮的完整流转：
 *   idle →（按下录音）recording →（松开/服务端 VAD 判停）waiting
 *        →（收到面试官回复）speaking →（音频播完）idle
 *
 * 关键取舍：
 * - **录音用 AudioWorklet 边录边推**，不是「录完整段再上传」：后端接的是火山的
 *   流式 ASR，越早开始推越早出识别结果。
 * - **播放用 Web Audio 排队**，不是 `<audio src>`：TTS 回来的是 24k PCM 分片，
 *   必须按顺序无缝拼接播放，否则每个分片各播各的、听起来像卡带。
 * - 播放状态（是否在播、播到第几毫秒、当前音量）集中暴露，头像层直接订阅——
 *   这是给 T7.9 口型动效留的口子，不要在按钮组件里重复实现一套。
 */

export type VoiceStatus = 'idle' | 'connecting' | 'recording' | 'waiting' | 'speaking' | 'error'

/** AudioWorklet 处理器源码：把麦克风的原始浮点帧转发到主线程。
 *  用内联源码 + Blob URL 的方式加载，避免为它单独配置构建产物路径。 */
const CAPTURE_WORKLET_SOURCE = `
class PcmCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0]
    if (channel && channel.length) {
      const copy = new Float32Array(channel.length)
      copy.set(channel)
      this.port.postMessage(copy, [copy.buffer])
    }
    return true
  }
}
registerProcessor('pcm-capture', PcmCaptureProcessor)
`

/** 波形显示的柱数（决定了组件里那一排竖条的个数） */
const WAVEFORM_BARS = 48

export function useVoiceInterview() {
  const status = ref<VoiceStatus>('idle')
  const connected = ref(false)
  const asrPartial = ref('')
  const asrFinal = ref('')
  const replyText = ref('')
  const interviewId = ref<number | null>(null)
  const errorMessage = ref('')
  // 演示环境的时长上限提示（T12.4）：不为空表示"这轮是被服务端到点结束的"。
  // 单独一个 ref 而不是塞进 errorMessage——这是正常结束，不是错误，界面上的处理也不同。
  const timeoutMessage = ref('')

  // 播放状态：头像层与波形都订阅它（T7.9 的口子）
  const playback = reactive({
    isPlaying: false,
    currentMs: 0,
    durationMs: 0,
    levels: [] as number[]
  })
  // 录制时的音量条（和播放分开，方便波形区分「谁在说」）
  const micLevels = ref<number[]>([])

  const sessionId = ref<number | null>(null)
  const sessionModel = ref(1)

  let socket: SpeechStreamConnection | null = null
  let audioContext: AudioContext | null = null
  let micStream: MediaStream | null = null
  let workletNode: AudioWorkletNode | null = null
  let micSource: MediaStreamAudioSourceNode | null = null
  // 录制缓冲（按输入采样率累积，攒够一包再降采样发出去）
  let pendingSamples: Float32Array[] = []
  let pendingLength = 0
  let inputSampleRate = 48000
  // 播放调度：下一个分片该从什么时候开始播
  let nextStartAt = 0
  let playbackStartedAt = 0
  let playbackTimer: number | null = null
  const activeSources = shallowRef<AudioBufferSourceNode[]>([])

  const canRecord = computed(() => connected.value && status.value === 'idle')
  const isBusy = computed(() => status.value === 'waiting' || status.value === 'speaking')

  // ---------- 连接 ----------

  const handleEvent = (event: SpeechEvent) => {
    switch (event.type) {
      case 'ready':
        connected.value = true
        status.value = 'idle'
        break
      case 'asr_partial':
        asrPartial.value = event.text
        break
      case 'asr_final':
        asrFinal.value = event.text
        asrPartial.value = ''
        // 识别出完整一句：停止录音，等面试官这一轮的处理结果
        stopRecording()
        status.value = 'waiting'
        break
      case 'reply':
        replyText.value = event.text
        interviewId.value = event.interview_id
        break
      case 'tts_start':
        beginPlayback()
        status.value = 'speaking'
        break
      case 'tts_end':
        status.value = 'idle'
        break
      case 'interview_timeout':
        // 服务端到点结束：停止录音、记下提示、把界面切回可操作状态。
        // 面试记录已经被服务端结束（时长冻结），所以这里的收尾不需要再调 finish 接口。
        timeoutMessage.value = event.message
        if (event.interview_id) {
          interviewId.value = event.interview_id
        }
        stopRecording()
        status.value = 'idle'
        break
      case 'error':
        errorMessage.value = event.message
        ElMessage.warning(event.message)
        // 出错后回到可录音状态，别把用户卡住
        if (status.value !== 'recording') {
          status.value = 'idle'
        }
        break
    }
  }

  const connect = async (targetSessionId: number, targetSessionModel: number) => {
    if (socket) {
      return
    }
    sessionId.value = targetSessionId
    sessionModel.value = targetSessionModel
    status.value = 'connecting'
    socket = openSpeechStream(targetSessionId, targetSessionModel, {
      onEvent: handleEvent,
      onAudio: (chunk) => enqueueAudio(chunk),
      onSocketError: () => {
        errorMessage.value = '语音通道连接失败'
        status.value = 'error'
      },
      onClose: () => {
        connected.value = false
        if (status.value !== 'error') {
          status.value = 'idle'
        }
      }
    })
  }

  // ---------- 录音 ----------

  const ensureAudioContext = (): AudioContext => {
    if (!audioContext) {
      audioContext = new AudioContext()
    }
    return audioContext
  }

  const flushPending = () => {
    if (!socket || pendingLength === 0) {
      return
    }
    const merged = new Float32Array(pendingLength)
    let offset = 0
    for (const part of pendingSamples) {
      merged.set(part, offset)
      offset += part.length
    }
    pendingSamples = []
    pendingLength = 0

    const downsampled = downsampleTo16k(merged, inputSampleRate)
    micLevels.value = [...micLevels.value.slice(-(WAVEFORM_BARS - 1)), computeLevel(downsampled)]
    socket.sendAudio(floatToInt16Bytes(downsampled))
  }

  const startRecording = async () => {
    if (!socket || !connected.value || status.value !== 'idle') {
      return
    }
    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }
      })
    } catch {
      errorMessage.value = '拿不到麦克风权限，请检查浏览器授权'
      ElMessage.error(errorMessage.value)
      status.value = 'error'
      return
    }

    const ctx = ensureAudioContext()
    await ctx.resume()
    inputSampleRate = ctx.sampleRate
    const workletUrl = URL.createObjectURL(
      new Blob([CAPTURE_WORKLET_SOURCE], { type: 'application/javascript' })
    )
    try {
      await ctx.audioWorklet.addModule(workletUrl)
    } finally {
      URL.revokeObjectURL(workletUrl)
    }

    micSource = ctx.createMediaStreamSource(micStream)
    workletNode = new AudioWorkletNode(ctx, 'pcm-capture')
    const samplesPerChunk = Math.round((inputSampleRate * CHUNK_DURATION_MS) / 1000)
    workletNode.port.onmessage = (event: MessageEvent<Float32Array>) => {
      const frame = event.data
      pendingSamples.push(frame)
      pendingLength += frame.length
      // 攒够一个 200ms 包就发出去；多出来的部分留到下一包，保证分包均匀
      while (pendingLength >= samplesPerChunk) {
        flushPending()
      }
    }
    micSource.connect(workletNode)

    asrPartial.value = ''
    asrFinal.value = ''
    micLevels.value = []
    status.value = 'recording'
    socket.sendJson({ type: 'start_utterance' })
  }

  const stopRecording = () => {
    if (status.value !== 'recording') {
      return
    }
    flushPending()
    workletNode?.port.close()
    workletNode?.disconnect()
    workletNode = null
    micSource?.disconnect()
    micSource = null
    micStream?.getTracks().forEach((track) => track.stop())
    micStream = null
    micLevels.value = []
    // 主动告诉后端「说完了」，不必等服务端 VAD 判停——两条路都支持
    socket?.sendJson({ type: 'end_utterance' })
  }

  /** 文字兜底：跳过 ASR 直接发一句文本（调试或环境不支持麦克风时用） */
  const sendText = (text: string) => {
    if (!socket || !connected.value || !text.trim()) {
      return
    }
    asrFinal.value = text.trim()
    status.value = 'waiting'
    socket.sendJson({ type: 'text', text: text.trim() })
  }

  // ---------- 播放 ----------

  const beginPlayback = () => {
    const ctx = ensureAudioContext()
    nextStartAt = ctx.currentTime + 0.05
    playbackStartedAt = nextStartAt
    playback.isPlaying = true
    playback.currentMs = 0
    playback.durationMs = 0
    playback.levels = []
    activeSources.value = []
    startPlaybackTimer()
  }

  const startPlaybackTimer = () => {
    if (playbackTimer !== null) {
      return
    }
    const tick = () => {
      const ctx = audioContext
      if (!ctx || !playback.isPlaying) {
        playbackTimer = null
        return
      }
      const elapsed = (ctx.currentTime - playbackStartedAt) * 1000
      playback.currentMs = Math.max(0, Math.min(playback.durationMs, elapsed))
      playbackTimer = requestAnimationFrame(tick)
    }
    playbackTimer = requestAnimationFrame(tick)
  }

  const enqueueAudio = (chunk: ArrayBuffer) => {
    const ctx = ensureAudioContext()
    const bytes = new Uint8Array(chunk)
    const samples = int16BytesToFloat32(bytes)
    if (!samples.length) {
      return
    }

    // PCM 分片按 24k 采样率还原成 AudioBuffer；AudioContext 会自动重采样到设备采样率
    const buffer = ctx.createBuffer(1, samples.length, DOWNLINK_SAMPLE_RATE)
    buffer.copyToChannel(samples, 0)
    const source = ctx.createBufferSource()
    source.buffer = buffer
    source.connect(ctx.destination)
    const startAt = Math.max(ctx.currentTime + 0.02, nextStartAt)
    source.start(startAt)
    nextStartAt = startAt + buffer.duration
    activeSources.value = [...activeSources.value, source]
    source.onended = () => {
      activeSources.value = activeSources.value.filter((item) => item !== source)
      if (activeSources.value.length === 0) {
        playback.isPlaying = false
        playback.currentMs = playback.durationMs
      }
    }

    playback.durationMs += buffer.duration * 1000
    playback.levels = [...playback.levels.slice(-(WAVEFORM_BARS - 1)), computeLevel(samples)]
    if (!playback.isPlaying) {
      // tts_start 还没到就先收到音频（正常不会），兜底把状态立起来
      playback.isPlaying = true
      startPlaybackTimer()
    }
  }

  // ---------- 收尾 ----------

  const disconnect = () => {
    stopRecording()
    socket?.close()
    socket = null
    connected.value = false
    status.value = 'idle'
    activeSources.value.forEach((source) => {
      try {
        source.stop()
      } catch {
        // 已经播完的 source 再 stop 会抛错，忽略
      }
    })
    activeSources.value = []
    playback.isPlaying = false
    playback.currentMs = 0
    if (playbackTimer !== null) {
      cancelAnimationFrame(playbackTimer)
      playbackTimer = null
    }
  }

  onBeforeUnmount(disconnect)

  return {
    // 状态
    status,
    connected,
    canRecord,
    isBusy,
    asrPartial,
    asrFinal,
    replyText,
    interviewId,
    errorMessage,
    timeoutMessage,
    playback,
    micLevels,
    // 动作
    connect,
    startRecording,
    stopRecording,
    sendText,
    disconnect
  }
}
