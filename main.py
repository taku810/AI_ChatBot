#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Discord VoiceVOX チャットボット
ユーザーのステータスを監視し、ゲームプレイ中に複数キャラクターでボイスチャットを行うボット
"""

import os
import logging
from src.discord_bot import run_bot

if __name__ == "__main__":
    # logsディレクトリの作成
    os.makedirs("logs", exist_ok=True)
    
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
    
    logger.info("Discord VoiceVOX チャットボットを起動します...")
    run_bot()