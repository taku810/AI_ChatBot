import os
import json
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class CharacterManager:
    def __init__(self, config_path: str):
        """
        キャラクター管理クラス
        
        Args:
            config_path: キャラクター設定ファイルのパス
        """
        self.characters = []
        self.load_characters(config_path)
        self.conversation_history = []
        self.active_character = None
        self.last_character_switch = datetime.now()
        self.character_switch_interval = timedelta(seconds=30)
        
    def load_characters(self, config_path: str):
        """
        設定ファイルからキャラクターを読み込む
        
        Args:
            config_path: キャラクター設定ファイルのパス
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.characters = data.get('characters', [])
                logger.info(f"{len(self.characters)}人のキャラクターを読み込みました")
        except Exception as e:
            logger.error(f"キャラクター設定ファイルの読み込みエラー: {e}")
            raise
    
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