from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
import copy

# --- Зберігання даних ---
user_data = {}
scheduled_posts = []
posted_messages = {}  # ключ: message_id каналу, значення: dict з текстами кнопок

# --- Команди ---
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Привіт! 👋 Я бот для створення постів 'Правда чи Брехня'.\n"
        "Натисни /new щоб створити новий пост."
    )

def new_post(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"step": "photo"}
    update.message.reply_text("Надішли фото для поста (або напиши 'без фото'):")

# --- Обробка фото ---
def photo_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    step = user_data.get(chat_id, {}).get("step")
    if step != "photo":
        return

    if update.message.text and update.message.text.lower() == "без фото":
        user_data[chat_id]["photo"] = None
    elif update.message.photo:
        user_data[chat_id]["photo"] = update.message.photo[-1].file_id
    else:
        update.message.reply_text("Надішли фото або напиши 'без фото'.")
        return

    user_data[chat_id]["step"] = "question"
    update.message.reply_text("Тепер введи питання:")

# --- Обробка тексту ---
def text_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if chat_id not in user_data or "step" not in user_data[chat_id]:
        update.message.reply_text("Спочатку надішли /new щоб створити пост.")
        return

    step = user_data[chat_id]["step"]
    text = update.message.text

    if step == "question":
        user_data[chat_id]["question"] = text
        user_data[chat_id]["step"] = "truth_text"
        update.message.reply_text("Введи текст для кнопки 'Правда':")
    elif step == "truth_text":
        user_data[chat_id]["truth_text"] = text
        user_data[chat_id]["step"] = "false_text"
        update.message.reply_text("Введи текст для кнопки 'Брехня':")
    elif step == "false_text":
        user_data[chat_id]["false_text"] = text
        user_data[chat_id]["step"] = None

        # Кнопки для публікації або відкладення
        keyboard = [
            [InlineKeyboardButton("Публікувати зараз", callback_data="publish_now")],
            [InlineKeyboardButton("Відкласти публікацію", callback_data="schedule_post")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Оберіть, що зробити з постом:", reply_markup=reply_markup)

# --- Обʼєднана функція для фото і тексту ---
def photo_or_text_handler(update: Update, context: CallbackContext):
    if update.message.photo or (update.message.text and update.message.text.lower() == "без фото"):
        photo_handler(update, context)
    else:
        text_handler(update, context)

# --- Відправка поста у канал ---
def send_post_to_channel(context: CallbackContext, post_data):
    channel_id = "@checikavo"  # твій канал
    keyboard = [
        [
            InlineKeyboardButton("✅ Правда", callback_data="truth"),
            InlineKeyboardButton("❌ Брехня", callback_data="false")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if post_data.get("photo"):
        msg = context.bot.send_photo(
            chat_id=channel_id,
            photo=post_data["photo"],
            caption=post_data["question"],
            reply_markup=reply_markup
        )
    else:
        msg = context.bot.send_message(
            chat_id=channel_id,
            text=post_data["question"],
            reply_markup=reply_markup
        )

    # Зберігаємо текст кнопок по message_id
    posted_messages[msg.message_id] = {
        "truth_text": post_data["truth_text"],
        "false_text": post_data["false_text"]
    }

# --- Обробка кнопок ---
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    data_btn = query.data

    # Кнопки в каналі
    if data_btn in ["truth", "false"]:
        msg_id = query.message.message_id
        if msg_id in posted_messages:
            text = posted_messages[msg_id]["truth_text"] if data_btn == "truth" else posted_messages[msg_id]["false_text"]
            query.answer(text=text, show_alert=True)
        else:
            query.answer(text="✅ Правда" if data_btn=="truth" else "❌ Брехня", show_alert=True)

    # Кнопки в приваті для публікації
    elif data_btn == "publish_now":
        chat_id = query.message.chat.id
        post_data = user_data.get(chat_id)
        if post_data:
            send_post_to_channel(context, post_data)
            query.edit_message_text("✅ Пост опубліковано у канал!")
    elif data_btn == "schedule_post":
        chat_id = query.message.chat.id
        post_data = user_data.get(chat_id)
        if post_data:
            scheduled_posts.append(copy.deepcopy(post_data))
            query.edit_message_text("⏱ Пост збережено для публікації пізніше!")

# --- Відправка відкладених постів ---
def send_scheduled(update: Update, context: CallbackContext):
    if not scheduled_posts:
        update.message.reply_text("Немає відкладених постів.")
        return

    for post in scheduled_posts:
        send_post_to_channel(context, post)
    scheduled_posts.clear()
    update.message.reply_text("✅ Всі відкладені пости опубліковані!")

# --- Основна функція ---
def main():
    token = "8142345174:AAFd3Nw40QjNLcr2dc3C0LI6_g7DBmCdOZ4"
    updater = Updater(token=token, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("new", new_post))
    dp.add_handler(CommandHandler("send_scheduled", send_scheduled))
    dp.add_handler(MessageHandler(Filters.photo | Filters.text, photo_or_text_handler))
    dp.add_handler(CallbackQueryHandler(button))

    print("✅ Бот запущений!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
