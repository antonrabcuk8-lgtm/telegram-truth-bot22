from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
import copy

# КОНФІГУРАЦІЯ
# ⚠️ ЗАМІНІТЬ ЦЕ ВАШИМИ ДАНИМИ!
TELEGRAM_BOT_TOKEN = "8142345174:AAFd3Nw40QjNLcr2dc3C0LI6_g7DBmCdOZ4"
CHANNEL_ID = "@checikavo"  # Ваш канал у форматі @username або ID (-100...)

# --- Зберігання даних ---
# У реальному проекті варто використовувати базу даних, але для простоти залишимо in-memory
user_data = {}         # Зберігає поточний стан створення поста для кожного користувача
scheduled_posts = []   # Список постів, які потрібно опублікувати пізніше
posted_messages = {}   # Ключ: message_id каналу, Значення: dict з текстами відповідей

# --- Команди ---

def start(update: Update, context: CallbackContext):
    """Обробляє команду /start."""
    update.message.reply_text(
        "Привіт! 👋 Я бот для створення постів 'Правда чи Брехня'.\n"
        "Натисни /new, щоб створити новий пост."
    )

def new_post(update: Update, context: CallbackContext):
    """Обробляє команду /new та ініціює створення поста."""
    chat_id = update.message.chat_id
    user_data[chat_id] = {"step": "photo"}
    update.message.reply_text("Надішли фото для поста (або напиши 'без фото'):")

def send_scheduled(update: Update, context: CallbackContext):
    """Обробляє команду /send_scheduled для публікації відкладених постів."""
    global scheduled_posts
    
    if not scheduled_posts:
        update.message.reply_text("Немає відкладених постів.")
        return

    # Робимо копію, щоб можна було безпечно очистити оригінал
    posts_to_send = scheduled_posts[:]
    scheduled_posts.clear()
    
    for post in posts_to_send:
        # Додана перевірка для безпеки, хоча тут дані мають бути повні
        if "question" in post and "truth_text" in post and "false_text" in post:
            send_post_to_channel(context, post)

    update.message.reply_text(f"✅ Усі {len(posts_to_send)} відкладені пости опубліковано!")

# --- Допоміжні функції обробки повідомлень ---

def photo_handler(update: Update, context: CallbackContext):
    """Обробка фото або тексту 'без фото'."""
    chat_id = update.message.chat_id
    # Перевірка, чи користувач на потрібному кроці
    if user_data.get(chat_id, {}).get("step") != "photo":
        return

    if update.message.text and update.message.text.lower() == "без фото":
        user_data[chat_id]["photo"] = None
    elif update.message.photo:
        user_data[chat_id]["photo"] = update.message.photo[-1].file_id
    else:
        update.message.reply_text("Будь ласка, надішли фото або напиши 'без фото'.")
        return

    user_data[chat_id]["step"] = "question"
    update.message.reply_text("Тепер введи питання:")

def text_handler(update: Update, context: CallbackContext):
    """Обробка тексту для питання, тексту Правди та тексту Брехні."""
    chat_id = update.message.chat_id
    text = update.message.text
    
    # Перевірка на активну сесію
    if chat_id not in user_data or "step" not in user_data[chat_id]:
        # Якщо це звичайний текст, а не команда
        if update.message.text and not update.message.text.startswith('/'):
            update.message.reply_text("Спочатку надішли /new, щоб створити пост.")
        return

    step = user_data[chat_id]["step"]

    if step == "question":
        user_data[chat_id]["question"] = text
        user_data[chat_id]["step"] = "truth_text"
        update.message.reply_text("Введи текст для кнопки 'Правда' (текст, який побачить користувач при натисканні):")
    
    elif step == "truth_text":
        user_data[chat_id]["truth_text"] = text
        user_data[chat_id]["step"] = "false_text"
        update.message.reply_text("Введи текст для кнопки 'Брехня' (текст, який побачить користувач при натисканні):")
    
    elif step == "false_text":
        user_data[chat_id]["false_text"] = text
        user_data[chat_id]["step"] = None # Завершуємо крок
        
        # Кнопки для публікації або відкладення
        keyboard = [
            [InlineKeyboardButton("✅ Публікувати зараз", callback_data="publish_now")],
            [InlineKeyboardButton("⏱ Відкласти публікацію", callback_data="schedule_post")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Оберіть, що робити з постом:", reply_markup=reply_markup)

# --- Обʼєднана функція для фото і тексту ---
def photo_or_text_handler(update: Update, context: CallbackContext):
    """Спрямовує вхідне повідомлення до відповідного обробника."""
    # Обробка на кроці "photo"
    if update.message.photo or (update.message.text and update.message.text.lower() == "без фото"):
        photo_handler(update, context)
    # Обробка на інших кроках
    elif update.message.text:
        text_handler(update, context)

# --- Відправка поста у канал ---

def send_post_to_channel(context: CallbackContext, post_data):
    """Відправляє сформований пост у Telegram-канал."""
    # Використовуємо .get() з текстом за замовчуванням, щоб уникнути KeyError
    question_text = post_data.get("question", "⚠️ Помилка: Питання не знайдено.") 
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Правда", callback_data="truth"),
            InlineKeyboardButton("❌ Брехня", callback_data="false")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Якщо є фото, відправляємо фото з підписом
    if post_data.get("photo"):
        msg = context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=post_data["photo"],
            caption=question_text,
            reply_markup=reply_markup
        )
    # Інакше відправляємо просто повідомлення
    else:
        msg = context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=question_text,
            reply_markup=reply_markup
        )

    # Зберігаємо тексти кнопок по message_id для обробки натискань у каналі
    posted_messages[msg.message_id] = {
        "truth_text": post_data["truth_text"],
        "false_text": post_data["false_text"]
    }

# --- Обробка кнопок (CallbackQueryHandler) ---

def button(update: Update, context: CallbackContext):
    """Обробляє всі натискання Inline-кнопок."""
    query = update.callback_query
    data_btn = query.data

    # Обов'язково викликаємо answer() для закриття сповіщення про натискання
    query.answer() 

    # 1. Кнопки в каналі (Правда/Брехня)
    if data_btn in ["truth", "false"]:
        msg_id = query.message.message_id
        
        if msg_id in posted_messages:
            # Беремо заздалегідь збережений текст відповіді
            text = posted_messages[msg_id]["truth_text"] if data_btn == "truth" else posted_messages[msg_id]["false_text"]
            # Повторно викликаємо answer, але вже з текстом для спливаючого вікна
            query.answer(text=text, show_alert=True)
        else:
            # Резервна відповідь, якщо дані втрачені
            query.answer(text="⚠️ Відповідь не знайдено.", show_alert=True)

    # 2. Кнопки в приваті (Публікувати/Відкласти)
    elif data_btn in ["publish_now", "schedule_post"]:
        chat_id = query.message.chat.id
        post_data = user_data.get(chat_id)
        
        # 🛑 КЛЮЧОВА ПЕРЕВІРКА ДЛЯ УНИКНЕННЯ 'KeyError: 'question''
        if not post_data or "question" not in post_data or "truth_text" not in post_data or "false_text" not in post_data:
            query.edit_message_text(
                "❌ Помилка: Не вдалося знайти повні дані для поста. Спробуйте створити пост знову за допомогою /new.",
                reply_markup=None
            )
            return

        # Публікація зараз
        if data_btn == "publish_now":
            send_post_to_channel(context, post_data)
            query.edit_message_text("✅ Пост успішно опубліковано у канал!")
            # Очищаємо дані сесії після успішної дії
            del user_data[chat_id]
            
        # Відкласти публікацію
        elif data_btn == "schedule_post":
            # Зберігаємо повну копію даних
            scheduled_posts.append(copy.deepcopy(post_data))
            query.edit_message_text("⏱ Пост збережено для публікації пізніше! Використайте /send_scheduled для публікації.")
            # Очищаємо дані сесії
            del user_data[chat_id]

# --- Основна функція запуску ---

def main():
    """Запускає бота."""
    # Створюємо Updater та передаємо токен
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Додавання обробників команд
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("new", new_post))
    dp.add_handler(CommandHandler("send_scheduled", send_scheduled))
    
    # Додавання обробника повідомлень (фото та текст)
    # Filters.photo | Filters.text обробляє і фото, і текст.
    dp.add_handler(MessageHandler(Filters.photo | Filters.text, photo_or_text_handler))
    
    # Додавання обробника натискань Inline-кнопок
    dp.add_handler(CallbackQueryHandler(button))

    print("✅ Бот запущений та готовий до роботи!")
    # Початок опитування Telegram щодо нових оновлень
    updater.start_polling()
    # Блокуємо виконання, поки не буде натиснуто Ctrl+C
    updater.idle()

if __name__ == "__main__":
    main()
