/**
 * PCM 音频工具（T7.7 语音面试用）。
 *
 * 语音链路的音频参数是固定约定，集中写在一处，避免两头对不上：
 * - 上行（麦克风 → 后端 → 火山 ASR）：**16kHz / 16bit / 单声道**
 * - 下行（火山 TTS → 后端 → 前端播放）：**24kHz / 16bit / 单声道**
 *
 * 浏览器麦克风的采样率通常是 48kHz 或 44.1kHz，所以录制时要先重采样。
 */

/** 上行音频参数：与后端 `ASR_SAMPLE_RATE` 保持一致 */
export const UPLINK_SAMPLE_RATE = 16000

/** 下行音频参数：与后端 `TTS_SAMPLE_RATE` 保持一致 */
export const DOWNLINK_SAMPLE_RATE = 24000

/** 每包音频时长（毫秒）：与后端建议的 200ms 分包一致 */
export const CHUNK_DURATION_MS = 200

/**
 * 把任意采样率的单声道浮点音频重采样到 16kHz。
 *
 * 用「窗口平均」而不是直接抽点：直接抽点会把高频折返成噪声，
 * 平均相当于一个简单的抗混叠低通，对语音识别足够，代价也只有一次遍历。
 */
export function downsampleTo16k(input: Float32Array, inputRate: number): Float32Array {
  if (inputRate === UPLINK_SAMPLE_RATE) {
    return input
  }
  const ratio = inputRate / UPLINK_SAMPLE_RATE
  const outputLength = Math.floor(input.length / ratio)
  const output = new Float32Array(outputLength)
  for (let i = 0; i < outputLength; i += 1) {
    const start = Math.floor(i * ratio)
    const end = Math.min(input.length, Math.floor((i + 1) * ratio))
    let sum = 0
    for (let j = start; j < end; j += 1) {
      sum += input[j]
    }
    output[i] = end > start ? sum / (end - start) : 0
  }
  return output
}

/**
 * 浮点音频（-1~1）转 16bit 小端 PCM 字节。
 *
 * 超出范围的样本要截断而不是回绕：回绕会把一声爆音变成刺耳的噪声。
 */
export function floatToInt16Bytes(input: Float32Array): Uint8Array<ArrayBuffer> {
  const buffer = new ArrayBuffer(input.length * 2)
  const view = new DataView(buffer)
  for (let i = 0; i < input.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, input[i]))
    view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
  }
  return new Uint8Array(buffer)
}

/** 16bit 小端 PCM 字节转浮点音频，用于送给 Web Audio 播放。 */
export function int16BytesToFloat32(bytes: Uint8Array<ArrayBuffer>): Float32Array<ArrayBuffer> {
  // 样本数向下取整：奇数长度说明这一包被截断，丢掉最后一个字节
  const sampleCount = Math.floor(bytes.byteLength / 2)
  const view = new DataView(bytes.buffer, bytes.byteOffset, sampleCount * 2)
  const output = new Float32Array(sampleCount)
  for (let i = 0; i < sampleCount; i += 1) {
    output[i] = view.getInt16(i * 2, true) / 0x8000
  }
  return output
}

/** 计算音量（RMS，0~1），用于波形显示。 */
export function computeLevel(input: Float32Array): number {
  if (!input.length) {
    return 0
  }
  let sum = 0
  for (let i = 0; i < input.length; i += 1) {
    sum += input[i] * input[i]
  }
  return Math.min(1, Math.sqrt(sum / input.length) * 3)
}
