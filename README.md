# Discord VoiceVOX チャットボット

DiscordでゲームをプレイしているときにVoiceVOXの声で話しかけてくれるボットです。複数のキャラクターがチャットに参加しているような雰囲気を出します。

## 特徴

- Discordのステータスがゲームプレイ中になると反応
- ユーザーがボイスチャンネルに入ると、5秒後にボットも参加
- ユーザーがボイスチャンネルを退出して3分後にボットも退出
- VoiceVOXを使用して自然な音声で会話
- 複数のキャラクターが交代で会話（ツンデレな幼馴染など）
- プレイしているゲームに関連する話題で会話
- Google Gemini 2.0 Flash APIを使用した自然な会話生成

## 必要条件

- Python 3.8以上
- Discord Bot Token
- Google Gemini API Key
- VoiceVOX（ローカルにインストールまたはリモートサーバー）
- FFmpeg

## インストール方法

1. リポジトリをクローン
   ```
   git clone <repository-url>
   cd discord-voicevox-chatbot
   ```

2. 必要なパッケージをインストール
   ```
   pip install -r requirements.txt
   ```

3. VoiceVOXをインストール
   - [VoiceVOX公式サイト](https://voicevox.hiroshiba.jp/)からダウンロードしてインストール

4. 環境変数の設定
   - `.env.example`を`.env`にコピーし、必要な情報を入力
   ```
   cp .env.example .env
   ```

## 環境変数の設定

`.env`ファイルに以下の情報を設定してください：

```
# Discord Bot Token
DISCORD_TOKEN=your_discord_bot_token_here
# User ID to track
TARGET_USER_ID=your_discord_user_id_here
# Voice Channel ID
VOICE_CHANNEL_ID=your_voice_channel_id_here
# Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here
# VoiceVox Engine URL (デフォルトでは通常localhost:50021)
VOICEVOX_ENGINE_URL=http://localhost:50021
```

## キャラクター設定のカスタマイズ

`config/characters.json`ファイルを編集することで、キャラクターの設定をカスタマイズできます。

```json
{
  "characters": [
    {
      "name": "キャラクター名",
      "personality": "キャラクターの性格",
      "voicevox_speaker_id": 0, // VoiceVOXのスピーカーID
      "color": "FF69B4", // 色コード（埋め込みメッセージ用）
      "phrases": [
        "デフォルトのフレーズ1",
        "デフォルトのフレーズ2"
      ],
      "relationship": "ユーザーとの関係"
    }
  ]
}
```

## 使い方

1. VoiceVOXを起動

2. ボットを実行
   ```
   python main.py
   ```

3. Discordでゲームを開始し、ボイスチャンネルに参加すると、ボットが5秒後に参加して会話を始めます。

## 常時稼働させる方法

### Windowsの場合

1. バッチファイル(.bat)を作成
   ```batch
   @echo off
   cd /d "C:\path\to\AI_chatbot"
   python main.py
   pause
   ```

2. タスクスケジューラーで起動時に実行するように設定

### Linuxの場合

1. systemdのサービスを作成
   ```
   [Unit]
   Description=Discord VoiceVOX Chatbot
   After=network.target

   [Service]
   Type=simple
   User=<username>
   WorkingDirectory=/path/to/AI_chatbot
   ExecStart=/usr/bin/python3 /path/to/AI_chatbot/main.py
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

2. サービスを有効化して起動
   ```
   sudo systemctl enable discord-voicevox-chatbot.service
   sudo systemctl start discord-voicevox-chatbot.service
   ```

## トラブルシューティング

- ボットが反応しない場合は、`.env`ファイルの設定を確認してください。
- VoiceVOXが正常に動作しているか確認してください。
- ログファイル(`logs/bot.log`と`logs/main.log`)でエラーがないか確認してください。
- Discordボットに適切な権限が付与されているか確認してください。

## ライセンス

MITライセンス