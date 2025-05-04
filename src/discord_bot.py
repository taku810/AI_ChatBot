import os
import json
import logging
import asyncio
import random
import discord
import tempfile
from datetime import datetime, timedelta
from discord.ext import commands, tasks
from dotenv import load_dotenv

from voicevox_client import VoiceVoxClient
from gemini_client import GeminiClient
from character_manager import CharacterManager

# 環境変数の読み込み
load_dotenv()

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Discord botの設定
intents = discord.Intents.default()
intents.presences = True  # プレゼンス情報の取得許可
intents.message_content = True  # メッセージ内容の取得許可
intents.members = True  # メンバー情報の取得許可
intents.voice_states = True  # ボイスチャンネル状態の取得許可

bot = commands.Bot(command_prefix='!', intents=intents)

# 設定情報
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_USER_ID = int(os.getenv("TARGET_USER_ID", 0))
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID", 0))

# タイマーとフラグ
user_status = {
    "is_playing": False,
    "game_name": None,
    "in_voice_channel": False,
    "left_voice_at": None,
    "needs_greeting": False
}

# クライアントの初期化
voicevox_client = VoiceVoxClient()
gemini_client = GeminiClient()
character_manager = CharacterManager("config/characters.json")

# 音声接続管理
voice_client = None
audio_queue = asyncio.Queue()
is_speaking = False

@bot.event
async def on_ready():
    logger.info(f"{bot.user.name} としてログインしました!")
    check_user_status.start()
    process_audio_queue.start()

@tasks.loop(seconds=5.0)
async def check_user_status():
    """ユーザーの状態を監視するタスク"""
    global user_status, voice_client

    if TARGET_USER_ID == 0:
        logger.error("TARGET_USER_ID が設定されていません")
        return

    # ターゲットユーザーの取得
    user = bot.get_user(TARGET_USER_ID)
    if not user:
        logger.warning(f"ユーザー (ID: {TARGET_USER_ID}) が見つかりません")
        return

    # ユーザーのアクティビティ確認
    previous_game_name = user_status["game_name"]
    user_status["is_playing"] = False
    user_status["game_name"] = None

    for guild in bot.guilds:
        member = guild.get_member(TARGET_USER_ID)
        if member:
            # ゲームステータスの確認
            for activity in member.activities:
                if activity.type == discord.ActivityType.playing:
                    user_status["is_playing"] = True
                    user_status["game_name"] = activity.name
                    logger.info(f"ユーザーは {activity.name} をプレイ中です")
                    break

            # ボイスチャンネル状態の確認
            voice_state = member.voice
            previous_in_voice = user_status["in_voice_channel"]
            user_status["in_voice_channel"] = voice_state is not None

            # ユーザーがボイスチャンネルに入った場合
            if not previous_in_voice and user_status["in_voice_channel"]:
                user_status["needs_greeting"] = True
                logger.info("ユーザーがボイスチャンネルに入りました")
                # 5秒後にボイスチャンネルに接続
                await asyncio.sleep(5)
                await join_voice_channel(voice_state.channel)
                
            # ユーザーがボイスチャンネルから退出した場合
            elif previous_in_voice and not user_status["in_voice_channel"]:
                user_status["left_voice_at"] = datetime.now()
                logger.info("ユーザーがボイスチャンネルから退出しました")

    # ユーザーが退出してから3分経過したらボットも退出
    if user_status["left_voice_at"]:
        elapsed = datetime.now() - user_status["left_voice_at"]
        if elapsed > timedelta(minutes=3) and voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            voice_client = None
            user_status["left_voice_at"] = None
            logger.info("ユーザーの退出から3分経過したため、ボットもボイスチャンネルから退出しました")

    # ゲームが変わった場合にメッセージを用意
    if user_status["game_name"] != previous_game_name and voice_client and voice_client.is_connected():
        if user_status["is_playing"]:
            logger.info(f"ゲーム変更を検出: {user_status['game_name']}")
            await generate_and_queue_response(user_status["game_name"])

    # 挨拶が必要な場合
    if user_status["needs_greeting"] and voice_client and voice_client.is_connected():
        await generate_and_queue_response(user_status["game_name"])
        user_status["needs_greeting"] = False

@tasks.loop(seconds=1.0)
async def process_audio_queue():
    """音声キューを処理するタスク"""
    global is_speaking, voice_client
    
    if not voice_client or not voice_client.is_connected():
        return
        
    if not is_speaking and not audio_queue.empty():
        is_speaking = True
        audio_path = await audio_queue.get()
        
        try:
            # 音声ファイルの再生
            if os.path.exists(audio_path):
                voice_client.play(discord.FFmpegPCMAudio(audio_path), after=lambda e: asyncio.run_coroutine_threadsafe(on_audio_finished(audio_path, e), bot.loop))
                logger.info(f"音声再生開始: {audio_path}")
            else:
                logger.error(f"音声ファイルが存在しません: {audio_path}")
                is_speaking = False
        except Exception as e:
            logger.error(f"音声再生中にエラーが発生しました: {e}")
            is_speaking = False

async def on_audio_finished(audio_path, error):
    """音声再生が完了したときのコールバック"""
    global is_speaking
    
    # 一時ファイルの削除
    try:
        if os.path.exists(audio_path):
            os.remove(audio_path)
            logger.debug(f"一時ファイルを削除しました: {audio_path}")
    except Exception as e:
        logger.error(f"一時ファイルの削除中にエラーが発生しました: {e}")
    
    if error:
        logger.error(f"音声再生中にエラーが発生しました: {error}")
    
    # スピーキングフラグの解除
    is_speaking = False

async def join_voice_channel(channel):
    """指定されたボイスチャンネルに接続する"""
    global voice_client
    
    if voice_client and voice_client.is_connected():
        if voice_client.channel.id == channel.id:
            return  # 既に接続済み
        await voice_client.disconnect()
    
    try:
        voice_client = await channel.connect()
        logger.info(f"ボイスチャンネル '{channel.name}' に接続しました")
    except Exception as e:
        logger.error(f"ボイスチャンネルへの接続中にエラーが発生しました: {e}")

async def generate_and_queue_response(game_name=None):
    """応答を生成して音声キューに追加する"""
    try:
        # アクティブなキャラクターを取得
        character = character_manager.get_active_character()
        
        # Geminiで応答を生成
        response_text = await gemini_client.generate_response(
            character_info=character,
            user_activity=game_name,
            conversation_history=character_manager.get_conversation_history()
        )
        
        # 会話履歴に記録
        character_manager.record_conversation(character['name'], response_text)
        logger.info(f"{character['name']}: {response_text}")
        
        # VoiceVOXで音声を生成
        audio_path = await voicevox_client.text_to_speech(response_text, character['voicevox_speaker_id'])
        
        if audio_path:
            # 音声キューに追加
            await audio_queue.put(audio_path)
            
            # テキストチャンネルにも送信（オプション）
            # テキストチャンネルがある場合は以下のコードを有効にする
            # text_channel = bot.get_channel(TEXT_CHANNEL_ID)
            # if text_channel:
            #     embed = discord.Embed(
            #         description=response_text,
            #         color=int(character['color'], 16)
            #     )
            #     embed.set_author(name=character['name'])
            #     await text_channel.send(embed=embed)
    except Exception as e:
        logger.error(f"応答生成中にエラーが発生しました: {e}")

def run_bot():
    """Botを起動する"""
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN が設定されていません")
        return
        
    if TARGET_USER_ID == 0:
        logger.error("TARGET_USER_ID が設定されていません")
        return
        
    if VOICE_CHANNEL_ID == 0:
        logger.warning("VOICE_CHANNEL_ID が設定されていません。自動チャンネル参加機能は動作しません")
    
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Botの実行中にエラーが発生しました: {e}")

if __name__ == "__main__":
    # logs ディレクトリの作成
    os.makedirs("logs", exist_ok=True)
    
    # Botの起動
    run_bot()