"""火山引擎语音服务客户端（对应 T7.6）。

- `protocol`：ASR / TTS 共用的二进制帧编解码
- `asr_client`：实时语音识别（双向流式）
- `tts_client`：双向流式语音合成
"""

from .asr_client import AsrSession, AsrTranscript
from .tts_client import TtsAudioChunk, TtsSession, TtsSubtitleWord

__all__ = [
    "AsrSession",
    "AsrTranscript",
    "TtsSession",
    "TtsAudioChunk",
    "TtsSubtitleWord",
]
