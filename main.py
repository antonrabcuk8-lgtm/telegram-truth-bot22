from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
import uuid

# Стани для ConversationHandler
PHOTO, QUESTION, TRUTH_TEXT, FALSE_TEXT = range(4)

# Глобальний словник для збереження постів
post_answers = {}
scheduled_posts = []

# --- Функції для розмови ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт! 👋 Я бот для створення постів 'Правда чи Брехня'.\n"
        "Натисни /new щоб створити новий пост або /cancel для скасування."
    )

async def new_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post_data'] = {}
    await update.message.reply_text("Надішли фото для поста (або напиши 'без фото'):")
    return PHOTO

async def photo_or_no_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['post_data']['photo'] = update.message.photo[-1].file_id
    elif update.message.text.lower() == "без фото":
        context.user_data['post_data']['photo'] = None
    else:
        await update.message.reply_text("Будь ласка, надішли фото або напиши 'без фото'.")
        return PHOTO

    await update.message.reply_text("Тепер введи питання:")
    return QUESTION

async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post_data']['question'] = update.message.text
    await update.message.reply_text("Введи текст для 'Правда':")
    return TRUTH_TEXT

async def get_truth_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post_data']['truth_text'] = update.message.text
    await update.message.reply_text("Введи текст для 'Брехня':")
    return FALSE_TEXT

async def get_false_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post_data']['false_text'] = update.message.text

    # Генеруємо унікальний UUID для поста
    post_uuid = str(uuid.uuid4())
    post_data = context.user_data['post_data']
    post_answers[post_uuid] = {
        "truth_text": post_data["truth_text"],
        "false_text": post_data["false_text"]
    }

    # Кнопки для перегляду та публікації
    keyboard = [
        [InlineKeyboardButton("Переглянути пост", callback_data=f"preview_{post_uuid}")],
        [InlineKeyboardButton("Публікувати зараз", callback_data=f"publish_{post_uuid}")],
        [InlineKeyboardButton("Відкласти публікацію", callback_data=f"schedule_{post_uuid}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Пост готовий. Оберіть дію:", reply_markup=reply_markup)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Створення поста скасовано.")
    context.user_data.clear()
    return ConversationHandler.END

# --- Обробка кнопок ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # обов'язково відповісти Telegram
    data = query.data

    post_uuid = data.split("_")[-1]  # витягуємо UUID поста

    if data.startswith("preview_"):
        await send_post_to_user_chat(context, query.message.chat_id, post_uuid)

    elif data.startswith("publish_"):
        await send_post_to_channel(context, post_uuid)
        await query.edit_message_text("✅ Пост опубліковано у канал!")
        post_answers.pop(post_uuid, None)

    elif data.startswith("schedule_"):
        scheduled_posts.append(post_uuid)
        await query.edit_message_text("⏱ Пост збережено для публікації пізніше!")
    
    elif data.startswith("truth_"):
        text = post_answers.get(post_uuid, {}).get("truth_text", "✅ Це правда!")
        await query.answer(text=text, show_alert=True)

    elif data.startswith("false_"):
        text = post_answers.get(post_uuid, {}).get("false_text", "❌ Це брехня!")
        await query.answer(text=text, show_alert=True)

# --- Відправка поста у канал ---
async def send_post_to_channel(context: ContextTypes.DEFAULT_TYPE, post_uuid):
    post_data = post_answers.get(post_uuid)
    if not post_data:
        return

    channel_id = "@ТВОЙ_КАНАЛ"  # заміни на свій канал

    keyboard = [
        [
            InlineKeyboardButton("✅ Правда", callback_data=f"truth_{post_uuid}"),
            InlineKeyboardButton("❌ Брехня", callback_data=f"false_{post_uuid}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if post_data.get("photo"):
        await context.bot.send_photo(chat_id=channel_id, photo=post_data["photo"],
                                     caption=post_data["question"], reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=channel_id, text=post_data["question"],
                                       reply_markup=reply_markup)

# --- Відправка поста для перегляду користувачу ---
async def send_post_to_user_chat(context: ContextTypes.DEFAULT_TYPE, chat_id, post_uuid):
    post_data = post_answers.get(post_uuid)
    if not post_data:
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Правда", callback_data=f"truth_{post_uuid}"),
            InlineKeyboardButton("❌ Брехня", callback_data=f"false_{post_uuid}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if post_data.get("photo"):
        await context.bot.send_photo(chat_id=chat_id, photo=post_data["photo"],
                                     caption=post_data["question"], reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=chat_id, text=post_data["question"],
                                       reply_markup=reply_markup)

# --- Основна функція ---
def main():
    token = "ВАШ_ТОКЕН_БОТА"
    app = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("new", new_post)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO | filters.Regex("^без фото$"), photo_or_no_photo)],
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_question)],
            TRUTH_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_truth_text)],
            FALSE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_false_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(CommandHandler("start", start))

    print("✅ Бот запущений!")
    app.run_polling()

if __name__ == "__main__":
    main()
