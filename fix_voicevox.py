import os

# 新しいVoiceVoxClientの内容
new_content = """# filepath: c:\\Users\\taku8\\Desktop\\to practice\\AI_chatbot\\src\\voicevox_client.py
import os
import io
import logging
import requests
import asyncio
import tempfile
import concurrent.futures
import time
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class VoiceVoxClient:
    def __init__(self):
        # 環境変数からの設定読み込み
        self.engine_url = os.getenv("VOICEVOX_ENGINE_URL", "http://localhost:50021")
        self.speed_scale = float(os.getenv("VOICEVOX_SPEEDSCALE", 1.1))
        thread_count = int(os.getenv("VOICEVOX_THREAD_COUNT", 4))
        
        logger.info(f"VoiceVox Engine URL: {self.engine_url}")
        logger.info(f"VoiceVox Speed Scale: {self.speed_scale}")
        logger.info(f"VoiceVox Thread Count: {thread_count}")
        
        # 音声合成の並列処理用スレッドプール
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=thread_count)
        
        # 音声リクエストのキャッシュ（同じテキスト+話者IDに対する再合成を避けるため）
        self._cache = {}
        
        # エラーが続いた場合のリトライ用のカウンター
        self._error_count = 0
        self._last_success_time = time.time()
    
    def _generate_audio_sync(self, text, speaker_id):
        \"\"\"
        同期処理で音声を生成する（スレッドプール内で実行される）
        
        Args:
            text: 読み上げるテキスト
            speaker_id: 話者ID
            
        Returns:
            生成された音声データのパス
        \"\"\"
        try:
            # 音声合成用のクエリを作成
            query_payload = {
                "text": text,
                "speaker": speaker_id
            }
            
            # 音声合成用のクエリを実行
            query_response = requests.post(
                f"{self.engine_url}/audio_query",
                params=query_payload,
                timeout=10  # タイムアウト設定
            )
            query_response.raise_for_status()
            query_data = query_response.json()
            
            # 音声合成の速度向上のためにパラメータを調整
            query_data["speedScale"] = self.speed_scale
            query_data["outputSamplingRate"] = 24000  # サンプリングレートを下げる
            query_data["outputStereo"] = False  # モノラル出力
            query_data["prePhonemeLength"] = 0.1  # 音声合成前の無音部分を短くする
            query_data["postPhonemeLength"] = 0.1  # 音声合成後の無音部分を短くする
            
            # 音声合成を実行
            synthesis_payload = {
                "speaker": speaker_id,
                "enable_interrogative_upspeak": True  # 疑問文の自動調整を有効化
            }
            synthesis_response = requests.post(
                f"{self.engine_url}/synthesis",
                headers={"Content-Type": "application/json"},
                params=synthesis_payload,
                json=query_data,
                timeout=20  # タイムアウト設定
            )
            synthesis_response.raise_for_status()
            
            # 一時ファイルに保存
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(synthesis_response.content)
                return temp_file.name
                
            # エラーカウントリセット
            self._error_count = 0
            self._last_success_time = time.time()
        
        except Exception as e:
            # エラーカウント増加
            self._error_count += 1
            
            # エラーログ出力
            logger.error(f"音声生成エラー ({self._error_count}回目): {e}")
            
            # エラーが多発している場合は短い音声のみ生成
            if self._error_count > 5 and len(text) > 50:
                truncated_text = text[:50] + "..."
                logger.warning(f"エラー多発のため音声を短縮します: {truncated_text}")
                return self._generate_audio_sync(truncated_text, speaker_id)
                
            # 最後の成功から2分以上経過している場合はリトライ
            if time.time() - self._last_success_time > 120:
                logger.info("VoiceVox Engineに接続できない状態が続いています。サービスが起動しているか確認してください。")
            
            return None
    
    async def generate_audio(self, text, speaker_id):
        \"\"\"
        非同期で音声を生成する
        
        Args:
            text: 読み上げるテキスト
            speaker_id: 話者ID
            
        Returns:
            生成された音声データのパス
        \"\"\"
        # テキストが空の場合は何もしない
        if not text or not text.strip():
            return None
            
        # キャッシュキーを作成
        cache_key = f"{speaker_id}:{text}"
        
        # キャッシュに存在する場合はそれを返す
        if cache_key in self._cache and os.path.exists(self._cache[cache_key]):
            logger.debug(f"キャッシュから音声を使用: {text[:20]}...")
            return self._cache[cache_key]
            
        try:
            # スレッドプールを使った並列処理で実行
            loop = asyncio.get_running_loop()
            audio_path = await loop.run_in_executor(
                self.thread_pool,
                self._generate_audio_sync,
                text,
                speaker_id
            )
            
            # 成功した場合はキャッシュに保存
            if audio_path:
                self._cache[cache_key] = audio_path
                
            return audio_path
        except Exception as e:
            logger.error(f"音声生成呼び出しエラー: {e}")
            return None
    
    async def text_to_speech(self, text, speaker_id):
        \"\"\"
        テキストを音声に変換する（互換性のためのメソッド）
        
        Args:
            text: 読み上げるテキスト
            speaker_id: 話者ID
            
        Returns:
            生成された音声データのパス
        \"\"\"
        return await self.generate_audio(text, speaker_id)
    
    async def text_to_speech_parallel(self, text, speaker_id):
        \"\"\"
        テキストを音声に変換する（旧並列処理版と互換性を維持）
        
        Args:
            text: 読み上げるテキスト
            speaker_id: 話者ID
            
        Returns:
            生成された音声データのパス
        \"\"\"
        # 新しい実装に移行済みのため、単に generate_audio を呼び出す
        return await self.generate_audio(text, speaker_id)
    
    def cleanup_cache(self):
        \"\"\"
        不要になったキャッシュファイルを削除する
        \"\"\"
        removed = 0
        for key, path in list(self._cache.items()):
            if not os.path.exists(path):
                del self._cache[key]
                removed += 1
        
        if removed > 0:
            logger.info(f"{removed}個のキャッシュエントリを削除しました")
"""

# ファイルに書き込み
with open('src/voicevox_client.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("VoiceVoxClientを更新しました。")
