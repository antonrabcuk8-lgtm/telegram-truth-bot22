from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
import uuid

# Стани для ConversationHandler
PHOTO, QUESTION, TRUTH_TEXT, FALSE_TEXT = range(4)
post_answers = {}
scheduled_posts = []

# --- Функції для керування розмовою ---
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
        await update.message.reply_text("Тепер введи питання:")
        return QUESTION
    elif update.message.text and update.message.text.lower() == "без фото":
        context.user_data['post_data']['photo'] = None
        await update.message.reply_text("Тепер введи питання:")
        return QUESTION
    else:
        await update.message.reply_text("Будь ласка, надішли фото або напиши 'без фото'.")
        return PHOTO

async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post_data']['question'] = update.message.text
    await update.message.reply_text("Введи текст для 'Правда' (спливаюче вікно):")
    return TRUTH_TEXT

async def get_truth_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post_data']['truth_text'] = update.message.text
    await update.message.reply_text("Введи текст для 'Брехня' (спливаюче вікно):")
    return FALSE_TEXT

async def get_false_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post_data']['false_text'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("Переглянути пост", callback_data="preview_post")],
        [InlineKeyboardButton("Публікувати зараз", callback_data="publish_now")],
        [InlineKeyboardButton("Відкласти публікацію", callback_data="schedule_post")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Пост готовий. Оберіть, що зробити:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Створення поста скасовано.")
    context.user_data.clear()
    return ConversationHandler.END

# --- Обробка кнопок ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    query_data = query.data

    if query_data == "preview_post":
        await send_post_to_user_chat(context, query.message.chat_id, context.user_data.get('post_data', {}))
        keyboard = [
            [InlineKeyboardButton("Публікувати зараз", callback_data="publish_now")],
            [InlineKeyboardButton("Відкласти публікацію", callback_data="schedule_post")],
        ]
        await query.edit_message_text(
            "✅ Готовий пост надіслано вам для перегляду. Після перегляду оберіть, що з ним робити.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query_data.startswith("truth_"):
        post_uuid = query_data.split('_')[1]
        text = post_answers.get(post_uuid, {}).get("truth_text", "✅ Це правда!")
        await query.answer(text=text, show_alert=True)

    elif query_data.startswith("false_"):
        post_uuid = query_data.split('_')[1]
        text = post_answers.get(post_uuid, {}).get("false_text", "❌ Це брехня!")
        await query.answer(text=text, show_alert=True)

    elif query_data == "publish_now":
        post_data = context.user_data.get('post_data', {})
        if post_data:
            await send_post_to_channel(context, post_data)
            await query.edit_message_text("✅ Пост опубліковано у канал!")
            context.user_data.clear()

    elif query_data == "schedule_post":
        post_data = context.user_data.get('post_data', {})
        if post_data:
            scheduled_posts.append(post_data.copy())
            await query.edit_message_text("⏱ Пост збережено для публікації пізніше!")
            context.user_data.clear()

    elif query_data == "preview_truth":
        await query.answer(text=context.user_data.get('post_data', {}).get('truth_text', "✅ Це правда!"), show_alert=True)

    elif query_data == "preview_false":
        await query.answer(text=context.user_data.get('post_data', {}).get('false_text', "❌ Це брехня!"), show_alert=True)

# --- Відправка поста у канал ---
async def send_post_to_channel(context: ContextTypes.DEFAULT_TYPE, post_data):
    channel_id = "@checikavo"  # заміни на свій канал
    post_uuid = str(uuid.uuid4())
    keyboard = [
        [InlineKeyboardButton("✅ Правда", callback_data=f"truth_{post_uuid}"),
         InlineKeyboardButton("❌ Брехня", callback_data=f"false_{post_uuid}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    post_answers[post_uuid] = {
        "truth_text": post_data["truth_text"],
        "false_text": post_data["false_text"]
    }
    if post_data.get("photo"):
        await context.bot.send_photo(chat_id=channel_id, photo=post_data["photo"],
                                     caption=post_data["question"], reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=channel_id, text=post_data["question"],
                                       reply_markup=reply_markup)

# --- Відправка поста для перегляду ---
async def send_post_to_user_chat(context: ContextTypes.DEFAULT_TYPE, chat_id, post_data):
    keyboard = [
        [InlineKeyboardButton("✅ Правда", callback_data="preview_truth"),
         InlineKeyboardButton("❌ Брехня", callback_data="preview_false")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if post_data.get("photo"):
        await context.bot.send_photo(chat_id=chat_id, photo=post_data["photo"],
                                     caption=post_data["question"], reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=chat_id, text=post_data["question"],
                                       reply_markup=reply_markup)

# --- Відправка відкладених постів ---
async def send_scheduled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scheduled_posts:
        await update.message.reply_text("Немає відкладених постів.")
        return
    await update.message.reply_text("Починаю публікацію відкладених постів...")
    for post_data in scheduled_posts:
        await send_post_to_channel(context, post_data)
    scheduled_posts.clear()
    await update.message.reply_text("✅ Всі відкладені пости опубліковані!")

# --- Основна функція ---
def main():
    token = "8142345174:AAFd3Nw40QjNLcr2dc3C0LI6_g7DBmCdOZ4"  # твій токен
    app = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('new', new_post)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO | filters.Regex('^без фото$'), photo_or_no_photo)],
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_question)],
            TRUTH_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_truth_text)],
            FALSE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_false_text)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send_scheduled", send_scheduled))
    app.add_handler(CallbackQueryHandler(button))  # обробка всіх callback-кнопок

    print("✅ Бот запущений!")
    app.run_polling()

if __name__ == "__main__":
    main()
