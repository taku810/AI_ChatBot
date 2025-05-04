import os
import io
import logging
import requests
import asyncio
import tempfile
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class VoiceVoxClient:
    def __init__(self):
        self.engine_url = os.getenv("VOICEVOX_ENGINE_URL", "http://localhost:50021")
        logger.info(f"VoiceVox Engine URL: {self.engine_url}")
        
        # 音声合成の並列処理用スレッドプール
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        
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
            
            # 音声合成の速度向上のためにパラメータを調整
            query_data["speedScale"] = 1.1  # 少し速く読み上げる
            query_data["outputSamplingRate"] = 24000  # サンプリングレートを下げる（デフォルトは44100）
            query_data["outputStereo"] = False  # モノラル出力
            
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
    
    async def text_to_speech_parallel(self, text, speaker_id):
        """
        テキストを音声に変換する（並列処理版）
        
        Args:
            text: 読み上げるテキスト
            speaker_id: 話者ID
            
        Returns:
            生成された音声データのパス
        """
        # 並列処理のためにスレッドプール内で実行
        loop = asyncio.get_running_loop()
        
        def _generate_audio_sync():
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
                
                # 音声合成の速度向上のためにパラメータを調整
                query_data["speedScale"] = 1.1  # 少し速く読み上げる
                query_data["outputSamplingRate"] = 24000  # サンプリングレートを下げる
                query_data["outputStereo"] = False  # モノラル出力
                query_data["prePhonemeLength"] = 0.1  # 音声合成前の無音部分を短くする（デフォルトは0.15）
                query_data["postPhonemeLength"] = 0.1  # 音声合成後の無音部分を短くする（デフォルトは0.15）
                
                # 音声合成を実行
                synthesis_payload = {
                    "speaker": speaker_id,
                    "enable_interrogative_upspeak": True  # 疑問文の自動調整を有効化
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
        
        # スレッドプールで並列実行
        return await loop.run_in_executor(self.thread_pool, _generate_audio_sync)