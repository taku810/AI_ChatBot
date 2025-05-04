import os
import json
import logging
import asyncio
import random
import discord
import tempfile
import threading
import time
from datetime import datetime, timedelta
from discord.ext import commands, tasks
from dotenv import load_dotenv

from .voicevox_client import VoiceVoxClient
from .gemini_client import GeminiClient
from .character_manager import CharacterManager

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
# 特権インテントが有効化されているか確認するための環境変数
USE_PRIVILEGED_INTENTS = os.getenv("USE_PRIVILEGED_INTENTS", "True").lower() == "true"

# 設定情報
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
TARGET_USER_ID = int(os.getenv("TARGET_USER_ID", 0))
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID", 0))
TEXT_CHANNEL_ID = int(os.getenv("TEXT_CHANNEL_ID", 0))
BOT_COUNT = int(os.getenv("BOT_COUNT", 1))  # 同時起動するボットの数

# ボットトークンの処理を改善
raw_tokens = os.getenv("BOT_TOKENS", "")
BOT_TOKENS = []
if raw_tokens:
    # カンマで区切り、空のトークンを除外
    for token in raw_tokens.split(","):
        if token.strip():
            BOT_TOKENS.append(token.strip())

# メインのDISCORD_TOKENがある場合は、それも含める
if DISCORD_TOKEN and DISCORD_TOKEN not in BOT_TOKENS:
    BOT_TOKENS.append(DISCORD_TOKEN)

# トークンがない場合のエラー表示
if not BOT_TOKENS:
    logger.error("有効なボットトークンが設定されていません。BOT_TOKENSかDISCORD_TOKENを環境変数に設定してください。")

# クライアントの初期化
voicevox_client = VoiceVoxClient()
gemini_client = GeminiClient()

# カスタムBotクラスの定義
class CharacterBot(commands.Bot):
    def __init__(self, bot_id):
        # インテントの設定
        intents = discord.Intents.default()
        if USE_PRIVILEGED_INTENTS:
            # 特権インテントを使用する場合（Discord Developer Portalで有効化する必要あり）
            logger.info("特権インテントを使用します。Discord Developer Portalで有効化されていることを確認してください。")
            intents.presences = True  # プレゼンス情報の取得許可
            intents.message_content = True  # メッセージ内容の取得許可
            intents.members = True  # メンバー情報の取得許可
        else:
            # 特権インテントを使用しない場合（機能が制限されます）
            logger.warning("特権インテントを使用しません。一部の機能が制限されます。")
            intents.presences = False
            intents.message_content = False
            intents.members = False

        intents.voice_states = True  # ボイスチャンネル状態の取得許可（これは特権インテントではない）
        
        super().__init__(command_prefix='!', intents=intents)
        
        # ボットの識別子とリソースを設定
        self.bot_id = bot_id
        self.character_manager = CharacterManager("config/characters.json")
        self.audio_queue = asyncio.Queue()
        self.voice_client = None
        self.is_speaking = False
        self.random_talk_cooldown = datetime.now()
        self.text_chat_cooldown = datetime.now()
        self.character = None
        
        # イベントハンドラを登録
        self.setup_events()
        
    def setup_events(self):
        # on_ready イベント
        @self.event
        async def on_ready():
            logger.info(f"Bot {self.bot_id} が {self.user.name} としてログインしました!")
            
            # キャラクターの割り当て
            if not self.character:
                assigned_characters = [bot.character for bot in bots if bot.character]
                
                available_characters = [c for c in self.character_manager.characters 
                                     if c['name'] not in [ac['name'] for ac in assigned_characters if ac]]
                
                if not available_characters:
                    available_characters = self.character_manager.characters
                    
                self.character = random.choice(available_characters)
                logger.info(f"Bot {self.bot_id} に {self.character['name']} を割り当てました")
            
            # タスクを開始
            if self.bot_id == 0:  # メインボット（0番）だけが状態監視を行う
                check_user_status.start(self)
            
            # 全てのボットが以下のタスクを実行
            process_audio_queue_task = tasks.loop(seconds=1.0)(self.process_audio_queue)
            process_audio_queue_task.start()
            
            random_voice_chat_task = tasks.loop(seconds=5.0)(self.random_voice_chat)
            random_voice_chat_task.start()
            
            random_text_chat_task = tasks.loop(seconds=15.0)(self.random_text_chat)
            random_text_chat_task.start()
        
        # on_message イベント
        @self.event
        async def on_message(message):
            # 自分のメッセージには反応しない
            if message.author == self.user:
                return
                
            # ユーザーからのメンション
            if self.user.mentioned_in(message):
                character = self.character
                user_activity = user_status["game_name"] if user_status["is_playing"] else None
                
                # Geminiで応答を生成
                response_text = await gemini_client.generate_response(
                    character_info=character,
                    user_activity=user_activity,
                    conversation_history=self.character_manager.get_conversation_history()
                )
                
                # 会話履歴に記録
                self.character_manager.record_conversation(character['name'], response_text)
                
                # 絵文字をランダムに付ける
                if random.random() < 0.5 and 'emoji' in character:
                    response_text += f" {random.choice(character['emoji'])}"
                    
                # メッセージを送信
                embed = discord.Embed(
                    description=response_text,
                    color=int(character['color'], 16)
                )
                embed.set_author(name=character['name'])
                await message.channel.send(embed=embed)
                
                # ボイスチャンネルに参加していれば音声も送信
                if self.voice_client and self.voice_client.is_connected():
                    await self.generate_and_queue_response(user_activity, response_text)

    async def process_audio_queue(self):
        """音声キューを処理するタスク"""
        if not self.voice_client or not self.voice_client.is_connected():
            return
            
        if not self.is_speaking and not self.audio_queue.empty():
            self.is_speaking = True
            audio_path = await self.audio_queue.get()
            
            try:
                # 音声ファイルの再生
                if os.path.exists(audio_path):
                    self.voice_client.play(discord.FFmpegPCMAudio(audio_path), 
                                    after=lambda e: asyncio.run_coroutine_threadsafe(
                                        self.on_audio_finished(audio_path, e), self.loop))
                    logger.info(f"Bot {self.bot_id} の音声再生開始: {audio_path}")
                else:
                    logger.error(f"音声ファイルが存在しません: {audio_path}")
                    self.is_speaking = False
            except Exception as e:
                logger.error(f"音声再生中にエラーが発生しました: {e}")
                self.is_speaking = False
    
    async def on_audio_finished(self, audio_path, error):
        """音声再生が完了したときのコールバック"""
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
        self.is_speaking = False
    
    async def random_voice_chat(self):
        """ランダムなタイミングで話題を振るタスク"""
        if not self.voice_client or not self.voice_client.is_connected():
            return
            
        # 既に話している場合はスキップ
        if self.is_speaking:
            return
            
        now = datetime.now()
        cooldown = random.randint(10, 20)  # 10〜20秒のランダムなクールダウン
        
        # クールダウン期間が過ぎていない場合はスキップ
        if (now - self.random_talk_cooldown).total_seconds() < cooldown:
            return
        
        # 他のボットが話しているかチェック
        any_speaking = any(bot.is_speaking for bot in bots)
        if any_speaking:
            return
        
        # 話題を生成する確率（10%）
        if random.random() < 0.1:
            self.random_talk_cooldown = now
            if self.character:
                game_name = user_status["game_name"] if user_status["is_playing"] else None
                await self.generate_and_queue_response(game_name)
    
    async def random_text_chat(self):
        """ランダムなタイミングでテキストチャットに話題を振るタスク"""
        if TEXT_CHANNEL_ID == 0:
            return
            
        now = datetime.now()
        cooldown = random.randint(300, 900)  # 5〜15分のランダムなクールダウン
        
        # クールダウン期間が過ぎていない場合はスキップ
        if (now - self.text_chat_cooldown).total_seconds() < cooldown:
            return
        
        # 話題を生成する確率（5%）
        if random.random() < 0.05:
            self.text_chat_cooldown = now
            if self.character:
                game_name = user_status["game_name"] if user_status["is_playing"] else None
                
                # Geminiで応答を生成
                response_text = await gemini_client.generate_response(
                    character_info=self.character,
                    user_activity=game_name,
                    conversation_history=self.character_manager.get_conversation_history()
                )
                
                # 会話履歴に記録
                self.character_manager.record_conversation(self.character['name'], response_text)
                
                # 絵文字をランダムに付ける
                if random.random() < 0.5 and 'emoji' in self.character:
                    response_text += f" {random.choice(self.character['emoji'])}"
                    
                # テキストチャンネルにメッセージを送信
                text_channel = self.get_channel(TEXT_CHANNEL_ID)
                if text_channel:
                    embed = discord.Embed(
                        description=response_text,
                        color=int(self.character['color'], 16)
                    )
                    embed.set_author(name=self.character['name'])
                    await text_channel.send(embed=embed)
    
    async def generate_and_queue_response(self, game_name=None, text=None):
        """応答を生成して音声キューに追加する"""
        try:
            # テキストが指定されていない場合はGeminiで生成
            if text is None:
                # Geminiで応答を生成
                text = await gemini_client.generate_response(
                    character_info=self.character,
                    user_activity=game_name,
                    conversation_history=self.character_manager.get_conversation_history()
                )
            
            # 会話履歴に記録
            self.character_manager.record_conversation(self.character['name'], text)
            logger.info(f"{self.character['name']} (Bot {self.bot_id}): {text}")
            
            # 並列処理で音声合成を高速化
            audio_path = await voicevox_client.text_to_speech_parallel(text, self.character['voicevox_speaker_id'])
            
            if audio_path:
                # 音声キューに追加
                await self.audio_queue.put(audio_path)
        except Exception as e:
            logger.error(f"応答生成中にエラーが発生しました: {e}")
    
    async def join_voice_channel(self, channel):
        """指定されたボイスチャンネルに接続する"""
        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.channel.id == channel.id:
                return  # 既に接続済み
            await self.voice_client.disconnect()
        
        try:
            self.voice_client = await channel.connect(cls=discord.VoiceClient)
            logger.info(f"Bot {self.bot_id} がボイスチャンネル '{channel.name}' に接続しました")
        except Exception as e:
            logger.error(f"ボイスチャンネルへの接続中にエラーが発生しました: {e}")

# タイマーとフラグ
user_status = {
    "is_playing": False,
    "game_name": None,
    "in_voice_channel": False,
    "left_voice_at": None,
    "needs_greeting": False,
    "online_status": False,
    "last_autonomous_join": None
}

# ボットのインスタンスを作成
bots = []

# トークン数に基づいてボットを作成（BOT_COUNTを上限とする）
max_bots = min(BOT_COUNT, len(BOT_TOKENS))
logger.info(f"作成するボットの数: {max_bots}")

for i in range(max_bots):
    if i < len(BOT_TOKENS) and BOT_TOKENS[i].strip():
        logger.info(f"Bot {i} を作成中...")
        bot = CharacterBot(i)
        bots.append(bot)
        logger.info(f"Bot {i} の作成完了")

if not bots and DISCORD_TOKEN:
    bot = CharacterBot(0)
    bots.append(bot)

# 音声認識関連
voice_recognition_active = False

@tasks.loop(seconds=5.0)
async def check_user_status(bot):
    """ユーザーの状態を監視するタスク（メインボット＝0番のみ実行）"""
    global user_status

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
    previous_online_status = user_status["online_status"]
    user_status["is_playing"] = False
    user_status["game_name"] = None
    user_status["online_status"] = False

    for guild in bot.guilds:
        member = guild.get_member(TARGET_USER_ID)
        if member:
            # オンラインステータスの確認
            user_status["online_status"] = str(member.status) != "offline"
            
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
                
                # 各ボットを5秒おきに順番にボイスチャンネルに接続
                for bot_instance in bots:
                    await asyncio.sleep(5)
                    await bot_instance.join_voice_channel(voice_state.channel)
                    
                    # 挨拶メッセージを用意
                    if bot_instance.character:
                        await bot_instance.generate_and_queue_response(user_status["game_name"])
                
            # ユーザーがボイスチャンネルから退出した場合
            elif previous_in_voice and not user_status["in_voice_channel"]:
                user_status["left_voice_at"] = datetime.now()
                logger.info("ユーザーがボイスチャンネルから退出しました")

    # ユーザーが退出してから3分経過したらボットも退出
    if user_status["left_voice_at"]:
        elapsed = datetime.now() - user_status["left_voice_at"]
        if elapsed > timedelta(minutes=3):
            for bot_instance in bots:
                if bot_instance.voice_client and bot_instance.voice_client.is_connected():
                    await bot_instance.voice_client.disconnect()
                    bot_instance.voice_client = None
                    
            user_status["left_voice_at"] = None
            logger.info("ユーザーの退出から3分経過したため、すべてのボットがボイスチャンネルから退出しました")

    # ゲームが変わった場合に各ボットにメッセージを用意
    if user_status["game_name"] != previous_game_name:
        if user_status["is_playing"]:
            logger.info(f"ゲーム変更を検出: {user_status['game_name']}")
            for bot_instance in bots:
                if bot_instance.voice_client and bot_instance.voice_client.is_connected():
                    # ランダムな待機時間を設定してボットごとに異なるタイミングで発言
                    await asyncio.sleep(random.uniform(1, 5))
                    await bot_instance.generate_and_queue_response(user_status["game_name"])
    
    # オンラインステータスが変わった場合
    if user_status["online_status"] != previous_online_status:
        if user_status["online_status"]:
            logger.info("ユーザーがオンラインになりました")
        else:
            logger.info("ユーザーがオフラインになりました")

def start_voice_recognition(bot):
    """音声認識を開始する（別スレッドで実行）"""
    global voice_recognition_active
    
    def voice_recognition_thread():
        global voice_recognition_active
        voice_recognition_active = True
        logger.info("音声認識スレッドを開始しました")
        
        try:
            # 音声認識の処理（実装は略）
            # 実際には音声認識ライブラリとDiscordの音声ストリームを連携させる必要がある
            while voice_recognition_active:
                # 音声認識処理がここに入る
                time.sleep(1)
        except Exception as e:
            logger.error(f"音声認識中にエラーが発生しました: {e}")
        finally:
            voice_recognition_active = False
    
    # 別スレッドで音声認識を実行
    threading.Thread(target=voice_recognition_thread, daemon=True).start()

async def autonomous_voice_join():
    """ユーザー不在でもボットが自律的にボイスチャンネルに参加するタスク"""
    # ユーザーがオンラインかつ、ボイスチャンネルにいない場合
    if (user_status["online_status"] and not user_status["in_voice_channel"] and
        VOICE_CHANNEL_ID != 0):
        
        now = datetime.now()
        # 前回の自律参加から30分以上経過しているか
        if (user_status["last_autonomous_join"] is None or
            (now - user_status["last_autonomous_join"]) > timedelta(minutes=30)):
            
            # ランダムなボットを選択
            if bots:
                bot = random.choice(bots)
                
                channel = bot.get_channel(VOICE_CHANNEL_ID)
                if channel:
                    await bot.join_voice_channel(channel)
                    user_status["last_autonomous_join"] = now
                    
                    # 参加メッセージを生成
                    if bot.character:
                        game_name = user_status["game_name"] if user_status["is_playing"] else None
                        await bot.generate_and_queue_response(game_name)
                        
                    # 30分後に自動退出するタイマーを設定
                    async def auto_leave():
                        await asyncio.sleep(30 * 60)  # 30分待機
                        # ユーザーが参加していない場合は退出
                        if not user_status["in_voice_channel"]:
                            if bot.voice_client and bot.voice_client.is_connected():
                                await bot.voice_client.disconnect()
                                bot.voice_client = None
                                logger.info(f"自律参加から30分経過したため、Bot {bot.bot_id} がボイスチャンネルから退出しました")
                    
                    asyncio.create_task(auto_leave())

def run_bots():
    """複数のBotを同時に起動する"""
    if not BOT_TOKENS:
        logger.error("BOT_TOKENS が設定されていません")
        return
        
    if TARGET_USER_ID == 0:
        logger.error("TARGET_USER_ID が設定されていません")
        return

    if not bots:
        logger.error("有効なボットが存在しません")
        return
    
    # 各Botを並列実行
    loop = asyncio.get_event_loop()
    
    # 各ボットの起動を確認するカウンター
    started_bots = 0
    
    # 各ボットを起動
    for i, bot in enumerate(bots):
        if i < len(BOT_TOKENS):
            token = BOT_TOKENS[i].strip()
            if token:
                # 各ボットを非同期で実行
                loop.create_task(bot.start(token))
                logger.info(f"Bot {i} の起動タスクを作成しました（トークン: {token[:5]}...）")
                started_bots += 1
    
    if started_bots == 0:
        logger.error("有効なトークンを持つボットがありません")
        return
    
    logger.info(f"{started_bots}個のボットを起動しました")
    
    # 自律的なボイスチャンネル参加タスクを登録
    async def autonomous_voice_join_task():
        while True:
            await asyncio.sleep(30)  # 初回は30秒待ってからチェック開始
            await autonomous_voice_join()
            await asyncio.sleep(300)  # その後は5分ごとにチェック
    
    loop.create_task(autonomous_voice_join_task())
    
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Botをシャットダウンしています...")
    finally:
        # 全てのボットをクリーンアップ
        for bot in bots:
            if bot._ready.is_set():  # ボットが初期化完了している場合のみクローズ
                loop.run_until_complete(bot.close())
        loop.close()

if __name__ == "__main__":
    # logs ディレクトリの作成
    os.makedirs("logs", exist_ok=True)
    
    # Botの起動
    run_bots()