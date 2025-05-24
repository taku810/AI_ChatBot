import speech_recognition as sr
import asyncio
import logging
from typing import Optional, Callable
import numpy as np

logger = logging.getLogger(__name__)

class VoiceRecognizer:
    def __init__(self, callback: Callable[[str], None]):
        self.recognizer = sr.Recognizer()
        self.callback = callback
        self.is_listening = False
        self.audio_threshold = 1000  # 音声検出の閾値

    async def start_listening(self):
        self.is_listening = True
        while self.is_listening:
            try:
                text = await self._listen_and_recognize()
                if text:
                    await self.callback(text)
            except Exception as e:
                logger.error(f"音声認識エラー: {e}")
                await asyncio.sleep(1)

    def stop_listening(self):
        self.is_listening = False

    async def _listen_and_recognize(self) -> Optional[str]:
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)
            try:
                logger.info("音声入力待機中...")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                # 音声データをNumPy配列に変換して振幅をチェック
                audio_data = np.frombuffer(audio.frame_data, dtype=np.int16)
                if np.max(np.abs(audio_data)) < self.audio_threshold:
                    return None

                text = await asyncio.to_thread(
                    self.recognizer.recognize_google,
                    audio,
                    language="ja-JP"
                )
                logger.info(f"認識されたテキスト: {text}")
                return text

            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                logger.debug("音声を認識できませんでした")
                return None
            except sr.RequestError as e:
                logger.error(f"音声認識サービスエラー: {e}")
                return None 