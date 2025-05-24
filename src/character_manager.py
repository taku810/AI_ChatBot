import os
import json
import logging
import random
import asyncio
from datetime import datetime, timedelta, time
from typing import Dict, List, Any, Optional
import pytz

logger = logging.getLogger(__name__)

class CharacterManager:
    def __init__(self, config_path: str = "config/characters.json"):
        """
        キャラクター管理クラス
        
        Args:
            config_path: キャラクター設定ファイルのパス
        """
        self.config_path = config_path
        self.characters = []
        self.schedule_windows = {}
        self.active_characters = set()
        self.conversation_history = []
        self.active_character = None
        self.last_character_switch = datetime.now()
        self.character_switch_interval = timedelta(seconds=30)
        self.load_config()
        
    def load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            self.characters = config['characters']
            self.schedule_windows = config['schedule_windows']

    def _is_time_in_window(self, current_time: datetime, window: Dict[str, str]) -> bool:
        start_time = datetime.strptime(window['start'], '%H:%M').time()
        end_time = datetime.strptime(window['end'], '%H:%M').time()
        current_time = current_time.time()
        
        if end_time < start_time:  # 日付をまたぐ場合
            return current_time >= start_time or current_time <= end_time
        return start_time <= current_time <= end_time

    def _get_activity_probability(self, character: Dict, current_time: datetime) -> float:
        base_probability = 0.3  # 基本確率
        
        # キャラクターのスケジュールに基づいて確率を調整
        for schedule in character['activity_schedule']:
            if schedule in self.schedule_windows and \
               self._is_time_in_window(current_time, self.schedule_windows[schedule]):
                base_probability = 0.8
                break
        
        return base_probability

    async def update_active_characters(self):
        while True:
            try:
                current_time = datetime.now(pytz.timezone('Asia/Tokyo'))
                new_active_characters = set()
                
                # アクティブなキャラクターの数を2-4人にランダムに決定
                target_active_count = random.randint(2, 4)
                
                # 各キャラクターの活動確率を計算
                character_probabilities = [
                    (char, self._get_activity_probability(char, current_time))
                    for char in self.characters
                ]
                
                # 確率に基づいてキャラクターを選択
                while len(new_active_characters) < target_active_count:
                    remaining_characters = [
                        (char, prob) for char, prob in character_probabilities
                        if char['id'] not in new_active_characters
                    ]
                    if not remaining_characters:
                        break
                        
                    for char, prob in remaining_characters:
                        if random.random() < prob and len(new_active_characters) < target_active_count:
                            new_active_characters.add(char['id'])
                
                # アクティブなキャラクターを更新
                self.active_characters = new_active_characters
                logger.info(f"アクティブなキャラクター: {self.active_characters}")
                
                # 30分ごとに更新
                await asyncio.sleep(1800)
                
            except Exception as e:
                logger.error(f"キャラクター更新エラー: {e}")
                await asyncio.sleep(60)

    def get_active_characters(self) -> List[Dict]:
        return [char for char in self.characters if char['id'] in self.active_characters]

    def get_all_characters(self) -> List[Dict]:
        """すべてのキャラクター情報を取得する"""
        return self.characters

    def is_character_active(self, character_id: str) -> bool:
        return character_id in self.active_characters
    
    def get_random_character(self, exclude=None):
        """
        ランダムなキャラクターを取得する（特定のキャラクターを除く）
        
        Args:
            exclude: 除外するキャラクター（オプション）
            
        Returns:
            ランダムに選ばれたキャラクター情報
        """
        available_characters = self.characters.copy()
        if exclude is not None:
            available_characters = [c for c in available_characters if c['name'] != exclude['name']]
        
        if not available_characters:
            return random.choice(self.characters)
        
        return random.choice(available_characters)
    
    def should_switch_character(self):
        """
        キャラクターを切り替えるべきかを判断する
        
        Returns:
            True: キャラクターを切り替えるべき場合
            False: それ以外の場合
        """
        now = datetime.now()
        return (now - self.last_character_switch) > self.character_switch_interval
    
    def switch_character(self):
        """
        発言するキャラクターを切り替える
        
        Returns:
            新しく選ばれたキャラクター情報
        """
        new_character = self.get_random_character(exclude=self.active_character)
        self.active_character = new_character
        self.last_character_switch = datetime.now()
        logger.info(f"キャラクターを切り替え: {new_character['name']}")
        return new_character
    
    def get_active_character(self):
        """
        現在アクティブなキャラクターを取得する
        初めて呼ばれた場合はランダムに選択する
        
        Returns:
            現在アクティブなキャラクター情報
        """
        if self.active_character is None or self.should_switch_character():
            return self.switch_character()
        return self.active_character
    
    def record_conversation(self, speaker: str, text: str):
        """
        会話履歴に追加する
        
        Args:
            speaker: 発言者の名前
            text: 発言内容
        """
        self.conversation_history.append({
            'speaker': speaker,
            'text': text,
            'timestamp': datetime.now().isoformat()
        })
        
        # 履歴が長すぎる場合は古いものを削除
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
    
    def get_conversation_history(self):
        """
        会話履歴を取得する
        
        Returns:
            会話履歴のリスト
        """
        return self.conversation_history

    def get_relation(self, char_id1: str, char_id2: str) -> str:
        """
        2人のキャラクター間の関係性を取得
        """
        char1 = next((c for c in self.characters if c['id'] == char_id1), None)
        if char1 and 'relations' in char1 and char_id2 in char1['relations']:
            return char1['relations'][char_id2]
        return "友達"

    def get_emotion(self, char_id: str) -> str:
        """
        キャラクターの現在の感情を取得
        """
        char = next((c for c in self.characters if c['id'] == char_id), None)
        if char and 'emotions' in char:
            return char['emotions'].get('current', 'neutral')
        return 'neutral'

    def set_emotion(self, char_id: str, emotion: str):
        """
        キャラクターの感情を変更
        """
        char = next((c for c in self.characters if c['id'] == char_id), None)
        if char and 'emotions' in char:
            char['emotions']['current'] = emotion

    def reset_emotions(self):
        """
        全キャラクターの感情をneutralにリセット
        """
        for char in self.characters:
            if 'emotions' in char:
                char['emotions']['current'] = 'neutral'