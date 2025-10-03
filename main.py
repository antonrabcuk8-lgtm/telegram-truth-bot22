# main.py
import asyncio
import json
import logging
import os
import uuid
from typing import Dict, List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ---------- Конфіг ----------
TOKEN = "8142345174:AAFd3Nw40QjNLcr2dc3C0LI6_g7DBmCdOZ4"   # <-- твій токен
CHANNEL_ID = "@checikavo"                                   # <-- твій канал
DATA_FILE = "data.json"
# ----------------------------

# Логи
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
PHOTO, QUESTION, TRUTH_TEXT, FALSE_TEXT = range(4)

# У пам'яті
post_answers: Dict[str, Dict] = {}
scheduled_posts: List[str] = []


# ---------- Збереження/завантаження ----------
def load_data():
    global post_answers, scheduled_posts
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            post_answers = data.get("post_answers", {})
            scheduled_posts = data.get("scheduled_posts", [])
            logger.info("Data loaded from %s", DATA_FILE)
        except Exception as e:
            logger.exception("Failed to load data file: %s", e)


def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"post_answers": post_answers, "scheduled_posts": scheduled_posts},
                f, ensure_ascii=False, indent=2
            )
        logger.info("Data saved to %s", DATA_FILE)
    except Exception as e:
        logger.exception("Failed to save data file: %s", e)


# ---------- Conversation ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт! 👋\n"
        "Я бот для створення постів «Правда чи Брехня».\n"
        "Команди:\n"
        "/new — створити новий пост\n"
        "/send_scheduled — опублікувати відкладені пости\n"
        "/cancel — скасувати створення поста"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Створення поста скасовано.")
    context.user_data.pop("post_data", None)
    return ConversationHandler.END


async def new_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["post_data"] = {}
    await update.message.reply_text("Надішли фото для поста (або напиши 'без фото'):")
    return PHOTO


async def photo_or_no_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    if update.message.photo:
        context.user_data["post_data"]["photo"] = update.message.photo[-1].file_id
    elif text.lower().strip() == "без фото":
        context.user_data["post_data"]["photo"] = None
    else:
        await update.message.reply_text("Будь ласка, надішли фото або напиши 'без фото'.")
        return PHOTO

    await update.message.reply_text("Тепер введи питання (текст поста):")
    return QUESTION


async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["post_data"]["question"] = update.message.text
    await update.message.reply_text("Введи текст для 'Правда':")
    return TRUTH_TEXT


async def get_truth_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["post_data"]["truth_text"] = update.message.text
    await update.message.reply_text("Введи текст для 'Брехня':")
    return FALSE_TEXT


async def get_false_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = context.user_data.get("post_data", {})
    post["false_text"] = update.message.text
    post_uuid = str(uuid.uuid4())
    post_answers[post_uuid] = {
        "question": post.get("question", ""),
        "truth_text": post.get("truth_text", "✅ Це правда!"),
        "false_text": post.get("false_text", "❌ Це брехня!"),
        "photo": post.get("photo", None),
        "creator_id": update.effective_user.id,
    }
    save_data()

    keyboard = [
        [InlineKeyboardButton("Переглянути пост", callback_data=f"preview_{post_uuid}")],
        [
            InlineKeyboardButton("Публікувати зараз", callback_data=f"publish_{post_uuid}"),
            InlineKeyboardButton("Відкласти", callback_data=f"schedule_{post_uuid}"),
        ],
    ]
    reply = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Пост готовий. Обери дію:", reply_markup=reply)

    context.user_data.pop("post_data", None)
    return ConversationHandler.END


# ---------- Callback ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    logger.info("Callback data: %s", data)

    action, _, rest = data.partition("_")

    if action == "preview" and rest:
        await send_post_preview_to_user(context, query.message.chat_id, rest)
    elif action == "publish" and rest:
        await send_post_to_channel(context, rest)
        await query.edit_message_text("✅ Пост опубліковано.")
    elif action == "schedule" and rest:
        if rest not in scheduled_posts and rest in post_answers:
            scheduled_posts.append(rest)
            save_data()
        await query.edit_message_text("⏱ Пост збережено для публікації.")
    elif action in ("truth", "false") and rest:
        post = post_answers.get(rest)
        if not post:
            await query.answer("Інформація про пост не знайдена.", show_alert=True)
            return
        text = post["truth_text"] if action == "truth" else post["false_text"]
        await query.answer(text=text, show_alert=True)


# ---------- Надсилання ----------
async def send_post_to_channel(context: ContextTypes.DEFAULT_TYPE, post_uuid: str):
    post = post_answers.get(post_uuid)
    if not post:
        return
    keyboard = [[
        InlineKeyboardButton("✅ Правда", callback_data=f"truth_{post_uuid}"),
        InlineKeyboardButton("❌ Брехня", callback_data=f"false_{post_uuid}")
    ]]
    reply = InlineKeyboardMarkup(keyboard)
    if post.get("photo"):
        await context.bot.send_photo(CHANNEL_ID, post["photo"], caption=post["question"], reply_markup=reply)
    else:
        await context.bot.send_message(CHANNEL_ID, post["question"], reply_markup=reply)


async def send_post_preview_to_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, post_uuid: str):
    post = post_answers.get(post_uuid)
    if not post:
        return
    keyboard = [
        [
            InlineKeyboardButton("✅ Правда", callback_data=f"truth_{post_uuid}"),
            InlineKeyboardButton("❌ Брехня", callback_data=f"false_{post_uuid}")
        ],
        [
            InlineKeyboardButton("Публікувати", callback_data=f"publish_{post_uuid}"),
            InlineKeyboardButton("Відкласти", callback_data=f"schedule_{post_uuid}")
        ]
    ]
    reply = InlineKeyboardMarkup(keyboard)
    if post.get("photo"):
        await context.bot.send_photo(chat_id, post["photo"], caption=post["question"], reply_markup=reply)
    else:
        await context.bot.send_message(chat_id, post["question"], reply_markup=reply)


# ---------- Команди ----------
async def send_scheduled_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scheduled_posts:
        await update.message.reply_text("Немає відкладених постів.")
        return
    for post_uuid in scheduled_posts.copy():
        await send_post_to_channel(context, post_uuid)
        scheduled_posts.remove(post_uuid)
    save_data()
    await update.message.reply_text("✅ Всі відкладені пости опубліковані.")


async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Бот працює. Постів: {len(post_answers)}, відкладених: {len(scheduled_posts)}"
    )


# ---------- Main ----------
def main():
    load_data()
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("new", new_post)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO | filters.Regex("^без фото$"), photo_or_no_photo)],
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_question)],
            TRUTH_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_truth_text)],
            FALSE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_false_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("send_scheduled", send_scheduled_command))
    app.add_handler(CommandHandler("health", health_check))

    logger.info("Starting bot...")
    app.run_polling()


if __name__ == "__main__":
    main()
