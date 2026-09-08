# -*- coding: utf-8 -*-
"""发声挂件（ADR-017：字/词级标准读音；整句留待"意"阶段。默认关闭）。

后端：edge-tts（GPL-3.0，联网，微软 Edge 语音服务）。后端可整体替换：
离线方案 piper-tts 因 espeak 数据路径在中文路径下的编码问题暂缓
（详见 docs/03 ADR，记为待办）。挂件默认关闭，核心词表不依赖本模块。
"""
from __future__ import annotations

import asyncio
from pathlib import Path


class VoicePlug:
    """字/词级发声：文本 → 音频文件。默认关闭。"""

    VOICE = "zh-CN-XiaoxiaoNeural"

    def __init__(self, voice: str | None = None):
        self.enabled = False
        self.voice = voice or self.VOICE

    @staticmethod
    def available() -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def enable(self, on: bool = True) -> None:
        self.enabled = bool(on)

    def speak(self, text: str, out_path: str, retries: int = 3) -> bool:
        """合成音频（mp3）。未启用或后端缺失返回 False。

        edge-tts 连接偶发失败（网络抖动），自动重试 retries 次。
        """
        if not self.enabled or not self.available():
            return False
        import edge_tts

        async def _go():
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(out_path)

        for attempt in range(1, retries + 1):
            try:
                asyncio.run(_go())
                if Path(out_path).exists() and Path(out_path).stat().st_size > 0:
                    return True
            except Exception:
                pass
            if attempt < retries:
                import time
                time.sleep(1.0 * attempt)
        return False
