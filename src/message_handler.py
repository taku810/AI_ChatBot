import asyncio
import logging
from typing import Dict, List, Optional
import json
import google.generativeai as genai
from datetime import datetime
import numpy as np
from .database.database import Database
from .character_manager import CharacterManager

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, db: Database, character_manager: CharacterManager, gemini_api_key: str):
        self.db = db
        self.character_manager = character_manager
        self.message_queue = asyncio.Queue()
        self.voice_queue = asyncio.Queue()
        self.last_message_time = {}
        self.cooldown = 6.0  # メッセージ送信の最小間隔（秒）
        
        # Gemini APIの設定
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
    def _calculate_importance(self, message: str) -> float:
        # メッセージの重要度を計算（0.0 - 1.0）
        # 文字数、質問文の有無、感情表現の有無などを考慮
        importance = 0.5
        
        # 文字数による重要度調整
        if len(message) > 100:
            importance += 0.2
        elif len(message) < 10:
            importance -= 0.2
            
        # 質問文による重要度調整
        if '？' in message or '?' in message:
            importance += 0.2
            
        # 感情表現による重要度調整
        emotion_keywords = ['！', '!', 'www', '笑', '泣', '😊', '😢', '❤️']
        if any(keyword in message for keyword in emotion_keywords):
            importance += 0.1
            
        return max(0.0, min(1.0, importance))

    async def process_message(self, user_id: str, message: str, character_id: str):
        # メッセージの重要度を計算
        importance = self._calculate_importance(message)
        
        # 重要なメッセージをデータベースに保存
        if importance > 0.6:
            session = await self.db.get_session()
            try:
                await self.db.add_interaction(session, user_id, message, importance, character_id)
            finally:
                await session.close()
        
        # ユーザーの過去の対話履歴を取得
        session = await self.db.get_session()
        try:
            history = await self.db.get_user_history(session, user_id, limit=5)
            personality = await self.db.get_user_personality(session, user_id)
        finally:
            await session.close()
        
        # キャラクター情報を取得
        character = next((c for c in self.character_manager.characters 
                         if c['id'] == character_id), None)
        if not character:
            return
        
        # Geminiへのプロンプトを構築
        prompt = self._build_prompt(message, history, personality, character)
        
        # 非同期でGeminiからの応答を取得
        response_future = asyncio.create_task(self._get_gemini_response(prompt))
        
        # 応答を待たずに音声合成をキューに追加
        await self.voice_queue.put({
            'character_id': character_id,
            'response_future': response_future
        })
        
        # 応答を待ってメッセージキューに追加
        response = await response_future
        await self.message_queue.put({
            'user_id': user_id,
            'character_id': character_id,
            'message': response,
            'timestamp': datetime.now()
        })
        self.update_emotion(character_id, response)

    def _build_prompt(self, message: str, history: List[Dict], personality: Dict, character: Dict) -> str:
        # キャラクター間の関係性（例：他のアクティブキャラとの関係）
        active_chars = self.character_manager.get_active_characters()
        relations = []
        for other in active_chars:
            if other['id'] != character['id']:
                rel = self.character_manager.get_relation(character['id'], other['id'])
                relations.append(f"{other['name']}：{rel}")
        relations_str = "\n".join(relations) if relations else "なし"
        # 感情
        emotion = self.character_manager.get_emotion(character['id'])
        prompt = f"""
あなたは以下の設定のキャラクターとして振る舞ってください：
名前: {character['name']}
性格: {character['personality']}
関係: {character['relationship_status']}
現在の感情: {emotion}
他キャラクターとの関係性:\n{relations_str}

ユーザーの特徴：
{json.dumps(personality, ensure_ascii=False, indent=2)}

最近の会話履歴：
{self._format_history(history)}

ユーザーからのメッセージ：
{message}

以下の点に注意して返信してください：
1. キャラクターの性格や口調を一貫して保ってください
2. ユーザーの過去の発言や特徴を考慮して返信してください
3. 他キャラクターとの関係性や感情も意識して会話してください
4. 返信は100文字以内に収めてください
"""
        return prompt

    def _format_history(self, history: List[Dict]) -> str:
        formatted = []
        for item in history:
            formatted.append(f"ユーザー: {item['message_content']}")
        return "\n".join(formatted)

    async def _get_gemini_response(self, prompt: str) -> str:
        try:
            response = await self.model.generate_content_async(prompt)
            return response.text[:100]  # 100文字以内に制限
        except Exception as e:
            logger.error(f"Gemini APIエラー: {e}")
            return "申し訳ありません、応答の生成に失敗しました。"

    async def can_send_message(self, character_id: str) -> bool:
        current_time = datetime.now()
        if character_id in self.last_message_time:
            elapsed = (current_time - self.last_message_time[character_id]).total_seconds()
            return elapsed >= self.cooldown
        return True

    async def process_voice_queue(self):
        while True:
            try:
                voice_data = await self.voice_queue.get()
                response = await voice_data['response_future']
                
                # ここで音声合成を実行（非同期）
                # 実装は省略（既存のVoiceVOX処理を使用）
                
                self.voice_queue.task_done()
            except Exception as e:
                logger.error(f"音声処理エラー: {e}")
                await asyncio.sleep(1)

    async def process_message_queue(self):
        while True:
            try:
                message_data = await self.message_queue.get()
                character_id = message_data['character_id']
                
                if await self.can_send_message(character_id):
                    # メッセージを送信（Discord APIを使用）
                    # 実装は省略（既存のDiscord送信処理を使用）
                    
                    self.last_message_time[character_id] = datetime.now()
                    
                self.message_queue.task_done()
            except Exception as e:
                logger.error(f"メッセージ処理エラー: {e}")
                await asyncio.sleep(1)

    def update_emotion(self, character_id: str, message: str):
        """
        メッセージ内容から簡易的に感情を変化させる（例：感嘆符や絵文字で喜び/怒り/悲しみなど）
        """
        emotion = 'neutral'
        if any(w in message for w in ['！', '!', '笑', '😊', 'www']):
            emotion = 'happy'
        elif any(w in message for w in ['怒', '💢']):
            emotion = 'angry'
        elif any(w in message for w in ['泣', '😢', '悲しい']):
            emotion = 'sad'
        self.character_manager.set_emotion(character_id, emotion) 