import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY environment variable is not set")
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
    async def generate_response(self, character_info, user_activity=None, conversation_history=None):
        """
        キャラクターとユーザーアクティビティに基づいた応答を生成する
        
        Args:
            character_info: キャラクター情報の辞書
            user_activity: ユーザーのアクティビティ（ゲーム名など）
            conversation_history: 過去の会話履歴（オプション）
            
        Returns:
            生成された応答テキスト
        """
        if conversation_history is None:
            conversation_history = []
        
        try:
            # プロンプトの構築
            character_prompt = f"""
            あなたは「{character_info['name']}」というキャラクターとしてロールプレイをします。

            ## キャラクター設定
            - 性格: {character_info['personality']}
            - 関係: {character_info['relationship']}

            ## 指示
            - あなたは「{character_info['name']}」として一人称で話してください。
            - 一つの発言は最大60文字までにしてください。
            - 感情表現は豊かに、キャラクターらしく振る舞ってください。
            - 返答する際は、必ず日本語で答えてください。
            """
            
            situation_prompt = ""
            if user_activity:
                situation_prompt = f"""
                ## 状況
                ユーザーは現在「{user_activity}」というゲームをプレイ中です。
                そのゲームについて言及したり、関連する話題で会話を始めてください。
                """
            else:
                situation_prompt = """
                ## 状況
                ユーザーは特にゲームをプレイしていません。
                ランダムな話題で会話を始めてください。日常的な話題や、ユーザーの調子を尋ねるのも良いでしょう。
                """
            
            # 過去の会話履歴を含める
            conversation_context = ""
            if conversation_history:
                conversation_context = "## 過去の会話\n"
                for entry in conversation_history[-3:]:  # 直近3つの会話のみ含める
                    conversation_context += f"{entry['speaker']}: {entry['text']}\n"
            
            full_prompt = f"{character_prompt}\n{situation_prompt}\n{conversation_context}\n\n{character_info['name']}としてユーザーに一言話しかけてください。"
            
            response = self.model.generate_content(full_prompt)
            
            # レスポンスの整形
            response_text = response.text.strip()
            
            # 長すぎる場合はカットする
            if len(response_text) > 100:
                response_text = response_text[:100] + "..."
                
            return response_text
            
        except Exception as e:
            logger.error(f"Gemini API エラー: {e}")
            # エラーの場合はキャラクターのデフォルトフレーズを返す
            import random
            return random.choice(character_info["phrases"])