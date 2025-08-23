This bot allows one to load videos from youtube and send them to telegram

0) **Install ffmpeg**

```bash
sudo apt update
sudo apt install ffmpeg
```


1) **Get API credentials**

- Go to https://my.telegram.org/apps
- Login with your phone number
- Create a new application
- Note down your `API_ID` and `API_HASH`



2) **Install Local Telegram Bot API Server
Using Docker (Easiest Method)**

```bash
# Pull the official image
docker pull aiogram/telegram-bot-api

# Run the server
docker run -d \
  --name telegram-bot-api \
  -p 8081:8081 \
  -e TELEGRAM_API_ID=<YOUR_API_ID> \
  -e TELEGRAM_API_HASH=<YOUR_API_HASH> \
  -v telegram-bot-api-data:/var/lib/telegram-bot-api \
  aiogram/telegram-bot-api
```

3) **Activate venv and install dependencies**

```bash
cd ./tg_bot_youtube_watch_later \
pyenv activate venv3.11.4 \
pip install -r requirements.txt
```

4) **Run bot**

```bash
python src/bot.py
```

or if you have cookies.txt file ([get cookies.txt file locally chrome extension](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)) from youtube then run like this:

```bash
python src/bot.py --cookies /path/to/youtube/cookies/file.txt
```

