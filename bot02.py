import os
import json
import asyncio
import random
import time
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Load Environment Variables ---
load_dotenv()
TELEGRAM_API_KEY = os.getenv("TELEGRAM_API_KEY")

if not TELEGRAM_API_KEY:
    raise ValueError("❌ TELEGRAM_API_KEY not found! Please set it in .env")

YOUTUBE_LINK = "https://www.youtube.com/@sscwalistudy?sub_confirmation=1"

# --- Bot Init ---
bot = Bot(token=TELEGRAM_API_KEY, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

# --- Global Variables ---
user_states = {}
cached_topics = {"gk": {}, "ca": {}}

# --- Cache Topics ---
def load_topics():
    """Folders se topics ko memory mein load karta hai."""
    for folder, key in [("gk_topics", "gk"), ("current_affairs", "ca")]:
        path = os.path.join(os.getcwd(), folder)
        if os.path.isdir(path):
            for filename in os.listdir(path):
                if filename.endswith(".json"):
                    file_path = os.path.join(path, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        title = data.get("title", filename.replace(".json", "").replace("_", " ").title())
                        
                        # Validate JSON format
                        if "questions" not in data or not isinstance(data["questions"], list):
                            logging.warning(f"Invalid JSON structure in {filename}, skipped.")
                            continue
                        
                        cached_topics[key][filename] = {"path": file_path, "title": title}
                        logging.info(f"Loaded: {title}")
                    except Exception as e:
                        logging.error(f"Error loading {filename}: {e}")
        else:
            logging.warning(f"Directory '{folder}' not found. Create it and add JSON files.")

load_topics()

# --- Utility Functions ---
def get_main_menu_markup():
    """Mukhya menu buttons banata hai."""
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🧠 GK TOPICS", callback_data="gk_menu"))
    builder.row(types.InlineKeyboardButton(text="📰 CURRENT AFFAIRS", callback_data="ca_menu"))
    builder.row(types.InlineKeyboardButton(text="➡️ SUBSCRIBE NOW", url=YOUTUBE_LINK))
    return builder.as_markup()

async def send_main_menu(chat_id):
    """Mukhya menu bhejta hai."""
    motivation = random.choice([
        "Mehnat itni karo ki kismat bhi bol uthe, 'Le le beta, isme tera hi haq hai!'",
        "Sapne woh nahi jo hum sote huye dekhte hain, sapne woh hain jo hamein sone nahi dete.",
        "Mushkilon se bhago mat, unka saamna karo!",
        "Koshish karne walon ki kabhi haar nahi hoti.",
    ])
    await bot.send_message(
        chat_id,
        f"**Welcome to DEEP STUDY QUIZ 📚**\n\n"
        f"💡 {motivation}\n\n"
        "Ab aap apne quiz ka subject chunein:",
        reply_markup=get_main_menu_markup()
    )

async def send_question(user_id, chat_id):
    """Agla quiz question bhejta hai."""
    state = user_states.get(user_id)
    if not state:
        await send_main_menu(chat_id)
        return

    questions = state['questions']
    idx = state['current_q_index']

    if idx >= len(questions):
        await end_quiz(user_id, chat_id)
        return

    q = questions[idx]

    # Validate question format
    if "question" not in q or "options" not in q or "answer" not in q:
        logging.error(f"Invalid question format: {q}")
        await bot.send_message(chat_id, "⚠️ Question format galat hai, skip kiya ja raha hai.")
        state['current_q_index'] += 1
        await send_question(user_id, chat_id)
        return

    builder = InlineKeyboardBuilder()
    for option in q['options']:
        builder.row(types.InlineKeyboardButton(text=option, callback_data=f"answer_{option}"))
    builder.row(types.InlineKeyboardButton(text="⏩ Skip Question", callback_data=f"skip_question"))

    sent_message = await bot.send_message(
        chat_id,
        f"**Question {idx+1}:**\n\n{q['question']}",
        reply_markup=builder.as_markup()
    )
    state['last_message_id'] = sent_message.message_id

async def start_quiz_from_file(user_id, chat_id, topic_path, topic_title):
    """File se quiz shuru karta hai."""
    try:
        with open(topic_path, 'r', encoding='utf-8') as f:
            topic_data = json.load(f)

        quiz_data = topic_data.get("questions", [])
        if not quiz_data:
            await bot.send_message(chat_id, "❌ Is topic me questions nahi mile.")
            await send_main_menu(chat_id)
            return

        random.shuffle(quiz_data)

        user_states[user_id] = {
            "questions": quiz_data,
            "current_q_index": 0,
            "score": 0,
            "correct_answers": 0,
            "incorrect_answers": 0,
            "attempted_questions": 0,
            "total_time_start": time.time(),
            "last_message_id": None
        }

        await bot.send_message(chat_id, f"📝 **{topic_title}**\n\nQuiz shuru ho raha hai...")
        await send_question(user_id, chat_id)

    except Exception as e:
        logging.error(f"Error starting quiz: {e}")
        await bot.send_message(chat_id, "❌ File read karne me error aaya.")
        await send_main_menu(chat_id)

async def end_quiz(uid, chat_id):
    """Quiz samapt hone par score bhejta hai."""
    state = user_states.pop(uid, None)
    if not state:
        return

    total_time = round(time.time() - state['total_time_start'])
    await bot.send_message(
        chat_id,
        f"**Quiz Samapt! 🎉**\n\n"
        f"🏆 Score: {state['score']}\n"
        f"✅ Sahi: {state['correct_answers']}\n"
        f"❌ Galat: {state['incorrect_answers']}\n"
        f"❓ Attempted: {state['attempted_questions']}\n"
        f"⏱️ Samay: {total_time} sec",
    )
    await send_main_menu(chat_id)

# --- Handlers (same as before, with logs for errors) ---
# [KEEP your handlers same, just add logging where needed]

# --- Main polling function ---
async def main() -> None:
    logging.info("Bot started polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())