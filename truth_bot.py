from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz

# --- Зберігання даних ---
user_data = {}
scheduled_posts = []

# --- Команди ---
def start(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("Створити новий пост", callback_data="new_post")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Привіт! 👋 Обери дію нижче:", reply_markup=reply_markup
    )

def new_post_start(chat_id, context: CallbackContext):
    user_data[chat_id] = {"step": "photo"}
    context.bot.send_message(chat_id=chat_id, text="Надішли фото для поста (або напиши 'без фото'):")

# --- Обробка фото ---
def photo_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    step = user_data.get(chat_id, {}).get("step")
    if step == "photo":
        if update.message.photo:
            user_data[chat_id]["photo"] = update.message.photo[-1].file_id
        elif update.message.text and update.message.text.lower() == "без фото":
            user_data[chat_id]["photo"] = None
        else:
            update.message.reply_text("Надішли фото або напиши 'без фото'.")
            return

        user_data[chat_id]["step"] = "question"
        update.message.reply_text("Тепер введи питання:")

# --- Обробка тексту ---
def text_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    if chat_id not in user_data or "step" not in user_data[chat_id]:
        update.message.reply_text("Натисни 'Створити новий пост', щоб почати.")
        return

    step = user_data[chat_id]["step"]
    text = update.message.text

    if step == "question":
        user_data[chat_id]["question"] = text
        user_data[chat_id]["step"] = "truth_text"
        update.message.reply_text("Введи текст для 'Правда':")
    elif step == "truth_text":
        user_data[chat_id]["truth_text"] = text
        user_data[chat_id]["step"] = "false_text"
        update.message.reply_text("Введи текст для 'Брехня':")
    elif step == "false_text":
        user_data[chat_id]["false_text"] = text
        user_data[chat_id]["step"] = "schedule_time"
        update.message.reply_text(
            "Вкажи час публікації у форматі ГГ:ХХ (24-годинний формат, наприклад 17:00):"
        )
    elif step == "schedule_time":
        try:
            hour, minute = map(int, text.split(":"))
            tz = pytz.timezone("Europe/Kiev")
            now = datetime.now(tz)
            publish_time = datetime(now.year, now.month, now.day, hour, minute, tzinfo=tz)
            if publish_time < now:
                update.message.reply_text("Час вже пройшов сьогодні. Вкажи майбутній час.")
                return
            user_data[chat_id]["publish_time"] = publish_time
            scheduled_posts.append(user_data[chat_id].copy())
            user_data[chat_id]["step"] = None
            update.message.reply_text(f"✅ Пост заплановано на {text}!")
        except:
            update.message.reply_text("Невірний формат часу. Напиши у форматі ГГ:ХХ.")

# --- Обробка кнопок ---
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat.id

    if query.data == "new_post":
        new_post_start(chat_id, context)

    query.answer()  # щоб спливаюче вікно не з'являлося як помилка

# --- Відправка поста ---
def send_post_to_channel(context: CallbackContext, post_data):
    channel_id = "@checikavo"
    keyboard = [
        [
            InlineKeyboardButton("✅ Правда", callback_data="truth"),
            InlineKeyboardButton("❌ Брехня", callback_data="false")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if post_data.get("photo"):
        context.bot.send_photo(chat_id=channel_id, photo=post_data["photo"], caption=post_data["question"], reply_markup=reply_markup)
    else:
        context.bot.send_message(chat_id=channel_id, text=post_data["question"], reply_markup=reply_markup)

# --- Планувальник для відкладених постів ---
def schedule_posts_job(context: CallbackContext):
    tz = pytz.timezone("Europe/Kiev")
    now = datetime.now(tz)
    to_publish = [p for p in scheduled_posts if p.get("publish_time") <= now]
    for post in to_publish:
        send_post_to_channel(context, post)
        scheduled_posts.remove(post)

# --- Основна функція ---
def main():
    token = "8142345174:AAFd3Nw40QjNLcr2dc3C0LI6_g7DBmCdOZ4"  # твій токен
    updater = Updater(token=token, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text, text_handler))
    dp.add_handler(MessageHandler(Filters.photo, photo_handler))

    # --- Scheduler ---
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Europe/Kiev"))
    scheduler.add_job(lambda: schedule_posts_job(updater.bot), 'interval', seconds=30)
    scheduler.start()

    print("✅ Бот запущений!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
