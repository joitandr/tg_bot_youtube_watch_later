import typing as t
import logging
import os
import tempfile
import subprocess
from dotenv import load_dotenv
from datetime import datetime
import re

import asyncio
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
# bot = Bot(token=os.getenv('BOT_TOKEN'))
# Change your bot initialization
# Initialize bot with local API server
logging.info(f"Initialize bot with local API server...")
bot = Bot(
    token=os.getenv('BOT_TOKEN'),
    session=AiohttpSession(
        api=TelegramAPIServer(
            base="http://localhost:8081/bot{token}/{method}",
            file="http://localhost:8081/file/bot{token}/{path}"
        )
    )
)
logging.info(f"Initialize bot with local API server: DONE")
dp = Dispatcher()

# Define states for conversation
class VideoDownloadStates(StatesGroup):
    waiting_for_link = State()

@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.reply(
        """
        This bot allows you to store videos from yutube in telegram to be watched later
        Use /get_video to download a video from yutube
        """
    )
    
@dp.message(Command('help'))
async def send_help(message: Message):
    help_text = (
        "Available commands:\n\n"
        "🔹 /start - Start the bot\n"
        "🔹 /help - Show this help message\n"
        "🔹 /get_video - Download a video from youtube\n"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)
    
@dp.message(Command('get_video'))
async def get_video(message: Message, state: FSMContext):
    await message.answer("Please send me a YouTube video link:")
    await state.set_state(VideoDownloadStates.waiting_for_link)

def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    return os.path.getsize(file_path)

# YouTube link validation pattern
YOUTUBE_LINK_PATTERN = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]+'    

@dp.message(StateFilter(VideoDownloadStates.waiting_for_link))
async def process_video_link(message: Message, state: FSMContext):
    # Get the link from the message
    link = message.text.strip()
    
    # Validate if it's a YouTube link
    if not re.match(YOUTUBE_LINK_PATTERN, link):
        await message.answer("That doesn't look like a valid YouTube link. Please send a valid YouTube link.")
        return
    
    # Send initial processing message with progress bar
    processing_msg = await message.answer("Initializing download...\n[                    ]\nSpeed: 0 KiB/s | ETA: 00:00")
    
    try:
        # Download the video with progress updates
        video_path = await download_youtube_video(link, message, processing_msg)
        
        file_size = get_file_size(video_path)
        file_size_mb = file_size / (1024 * 1024)
        
        logging.info(f"Video file size: {file_size_mb:.2f} MB")
        
        # Send the video to the user
        await message.answer("Here's your video:")
        with open(video_path, 'rb') as video_file:
            await message.answer_video(
                video=types.BufferedInputFile(
                    file=video_file.read(),
                    filename=os.path.basename(video_path)
                ),
                caption=f"Downloaded from: {link}"
            )
        
        # Clean up the temporary file
        os.remove(video_path)
        
        # Reset the state
        await state.clear()
        
    except Exception as e:
        logging.error(f"Error downloading video: {e}")
        await message.answer(f"Sorry, I couldn't download this video. Error: {str(e)}")
        await state.clear()
    
    # Delete the processing message
    try:
        await bot.delete_message(chat_id=processing_msg.chat.id, message_id=processing_msg.message_id)
    except Exception as e:
        logging.error(f"Error deleting processing message: {e}")
        # Continue execution even if we can't delete the message

async def download_youtube_video(url: str, message: Message = None, processing_msg: Message = None) -> str:
    """Download a YouTube video using yt-dlp and return the path to the downloaded file."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        # Set up yt-dlp command with progress
        command = [
            'yt-dlp',
            url,
            '-o', output_template,
            '-f', 'best[height<=720]',  # Limit quality to 720p to reduce file size
            '--geo-bypass',
            '--progress',
            '--newline'
        ]
        
        # Run the command
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Progress tracking variables
        progress_bar = "[                    ]"  # 20 spaces
        percentage = "0.0%"
        download_speed = "0 KiB/s"
        eta = "00:00"
        last_update_time = datetime.now()
        
        # Process output in real-time to update progress
        while True:
            line = await process.stdout.readline()
            if not line:
                break
                
            line_text = line.decode('utf-8', errors='replace').strip()
            
            # Parse progress information
            if '[download]' in line_text:
                # Extract percentage if available
                percent_match = re.search(r'(\d+\.\d+)%', line_text)
                if percent_match:
                    percent = float(percent_match.group(1))
                    # Update progress bar
                    filled_length = int(20 * percent / 100)
                    progress_bar = "[" + "█" * filled_length + " " * (20 - filled_length) + "]"
                    percentage = f"{percent:.1f}%"
                
                # Extract download speed
                speed_match = re.search(r'(\d+\.\d+ [KMG]iB/s)', line_text)
                if speed_match:
                    download_speed = speed_match.group(1)
                
                # Extract ETA
                eta_match = re.search(r'ETA (\d+:\d+)', line_text)
                if eta_match:
                    eta = eta_match.group(1)
                
                # Update progress message every 2 seconds to avoid Telegram API rate limits
                current_time = datetime.now()
                if (current_time - last_update_time).total_seconds() >= 2 and processing_msg:
                    progress_text = f"Downloading: {percentage}\n{progress_bar}\nSpeed: {download_speed} | ETA: {eta}"
                    try:
                        await bot.edit_message_text(
                            chat_id=processing_msg.chat.id,
                            message_id=processing_msg.message_id,
                            text=progress_text
                        )
                        last_update_time = current_time
                    except Exception as e:
                        logging.error(f"Error updating progress: {e}")
        
        # Get final status
        await process.wait()
        stderr_data = await process.stderr.read()
        
        if process.returncode != 0:
            raise Exception(f"yt-dlp error: {stderr_data.decode()}")
        
        # Find the downloaded file
        files = os.listdir(temp_dir)
        if not files:
            raise Exception("No files were downloaded")
        
        # Get the full path of the downloaded file
        video_path = os.path.join(temp_dir, files[0])
        
        # Copy to a location outside the temp directory so it doesn't get deleted
        permanent_path = os.path.join(os.getcwd(), 'downloads', os.path.basename(video_path))
        os.makedirs(os.path.dirname(permanent_path), exist_ok=True)
        
        # Use subprocess to copy the file (shutil might not work well with asyncio)
        copy_process = await asyncio.create_subprocess_exec(
            'cp', video_path, permanent_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await copy_process.communicate()
        
        # Update progress message to show completion
        if processing_msg:
            try:
                await bot.edit_message_text(
                    chat_id=processing_msg.chat.id,
                    message_id=processing_msg.message_id,
                    text="Download complete! Sending video..."
                )
            except Exception as e:
                logging.error(f"Error updating final progress: {e}")
        
        return permanent_path
    
    
async def main():
    while True:
        try:
            # Set up commands for the bot menu
            await bot.set_my_commands([
                types.BotCommand(command="start", description="Start the bot"),
                types.BotCommand(command="help", description="Show available commands"),
                types.BotCommand(command="get_video", description="Get a youtube video"),
            ])
            
            # Start polling with retry on connection errors
            await asyncio.gather(
                dp.start_polling(bot, polling_timeout=30),
            )
        except Exception as e:
            logging.error(f"Connection error: {e}")
            logging.info("Retrying in 5 seconds...")
            await asyncio.sleep(5)
            continue

# Run the bot
if __name__ == '__main__':
    asyncio.run(main())