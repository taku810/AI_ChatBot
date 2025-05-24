#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Discord VoiceVOX チャットボット
ユーザーのステータスを監視し、ゲームプレイ中に複数キャラクターでボイスチャットを行うボット
"""

import os
import logging
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from src.discord_bot import run_bots

def main():
    # 環境変数の読み込み
    load_dotenv()
    
    # logsディレクトリが存在しない場合は作成
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # ロギングの設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("logs/main.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    # 環境変数の確認
    required_env_vars = [
        'DISCORD_TOKEN', 'TARGET_USER_ID', 'VOICE_CHANNEL_ID', 
        'GEMINI_API_KEY', 'VOICEVOX_ENGINE_URL'
    ]

    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        logger.error(f"必要な環境変数が設定されていません: {', '.join(missing_vars)}")
        logger.error(".envファイルを確認してください")
        sys.exit(1)
    
    # 設定情報を表示
    logger.info("=== Discord VoiceVOX チャットボットを起動します ===")
    logger.info(f"アクティブボット比率: {os.getenv('ACTIVE_BOT_RATIO', 0.5)}")
    logger.info(f"ボットローテーション間隔: {os.getenv('BOT_ROTATION_INTERVAL', 30)}分")
    logger.info(f"ボット数: {os.getenv('BOT_COUNT', 1)}")
    
    # ボットを起動
    try:
        run_bots()
    except Exception as e:
        logger.error(f"実行中にエラーが発生しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()