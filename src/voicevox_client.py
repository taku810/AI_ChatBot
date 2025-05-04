import os
import io
import logging
import requests
import asyncio
import tempfile
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class VoiceVoxClient:
    def __init__(self):
        self.engine_url = os.getenv("VOICEVOX_ENGINE_URL", "http://localhost:50021")
        logger.info(f"VoiceVox Engine URL: {self.engine_url}")
        
    async def generate_audio(self, text, speaker_id):
        """
        VoiceVOXを使用して音声を生成する
        
        Args:
            text: 読み上げるテキスト
            speaker_id: 話者ID
            
        Returns:
            生成された音声データのパス
        """
        try:
            # 音声合成用のクエリを作成
            query_payload = {
                "text": text,
                "speaker": speaker_id
            }
            
            # 音声合成用のクエリを実行
            query_response = requests.post(
                f"{self.engine_url}/audio_query",
                params=query_payload
            )
            query_response.raise_for_status()
            query_data = query_response.json()
            
            # 音声合成を実行
            synthesis_payload = {
                "speaker": speaker_id
            }
            synthesis_response = requests.post(
                f"{self.engine_url}/synthesis",
                headers={"Content-Type": "application/json"},
                params=synthesis_payload,
                json=query_data
            )
            synthesis_response.raise_for_status()
            
            # 一時ファイルに保存
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(synthesis_response.content)
                return temp_file.name
        
        except Exception as e:
            logger.error(f"音声生成エラー: {e}")
            return None
        
    async def text_to_speech(self, text, speaker_id):
        """
        テキストを音声に変換するメインメソッド
        
        Args:
            text: 読み上げるテキスト
            speaker_id: 話者ID
            
        Returns:
            生成された音声データのパス
        """
        return await self.generate_audio(text, speaker_id)