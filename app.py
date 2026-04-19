import telebot
from flask import Flask, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from telebot import types
import os
import json

# ==================== TOKEN ====================
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ==================== GOOGLE SHEETS ====================
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)
sheet = client.open_by_key("1ghegwU8QA-JiARIMuFyiBAHyZGDw2238krqNhukzCrU").sheet1

# ==================== KANAL LINKLARI ====================
TELEGRAM_LINK = "https://t.me/sharqsupermarketi"
INSTAGRAM_LINK = "https://instagram.com/sharq.supermarketi"

# ==================== DATA ====================
user_data = {}       # yangi ro'yxatdan o'tish uchun
feedback_data = {}   # fikr qoldirish jarayoni uchun

# ==================== SAVOL VARIANTLARI ====================
LIKE_OPTIONS = [
    "🛒 Mahsulot tanlovi keng",
    "💰 Narxlar arzon",
    "👥 Xodimlar xushmuomala",
    "✨ Tozalik va tartib",
    "📍 Joylashuvi qulay",
    "⏰ Ish vaqti qulay",
    "✍️ Boshqa (yozish)"
]

DISLIKE_OPTIONS = [
    "🐌 Kassada navbat uzun",
    "💸 Ba'zi narxlar qimmat",
    "📦 Ba'zi mahsulotlar yo'q",
    "😐 Xodimlar munosabati",
    "🧹 Tozalik yetishmaydi",
    "🅿️ Parkovka muammoli",
    "✍️ Boshqa (yozish)"
]

WISH_OPTIONS = [
    "🚚 Uyga yetkazib berish",
    "📱 Mobil ilova",
    "🎁 Doimiy mijozlar uchun bonus tizimi",
    "🍰 Pishiriqxona yoki kafe",
    "🏪 Yangi filiallar ochilishi",
    "💳 Qulay to'lov turlari (Payme, Click)",
    "✍️ Boshqa (yozish)"
]

# ==================== YORDAMCHI FUNKSIYALAR ====================
def main_menu_keyboard():
    """4 tugmali asosiy menyu"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🎁 Chegirmani tekshirish"),
        types.KeyboardButton("💬 Fikr qoldirish")
    )
    markup.add(
        types.KeyboardButton("📷 Instagram"),
        types.KeyboardButton("📢 Telegram kanal")
    )
    return markup

def options_keyboard(options):
    """Savol variantlari uchun klaviatura"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for opt in options:
        markup.add(types.KeyboardButton(opt))
    return markup

def find_user(chat_id, phone=None):
    """Mijoz oldin ro'yxatdan o'tganmi tekshiradi (user_id yoki telefon bo'yicha)"""
    try:
        all_records = sheet.get_all_values()
        for row in all_records[1:]:  # 1-qator sarlavha
            if len(row) > 0 and str(row[0]) == str(chat_id):
                return row
            if phone and len(row) > 2 and row[2] and row[2].replace(" ", "") == phone.replace(" ", ""):
                return row
        return None
    except Exception as e:
        print("Find user error:", e)
        return None

# ==================== START ====================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id

    # Tozalash
    user_data.pop(chat_id, None)
    feedback_data.pop(chat_id, None)

    # Mijoz oldin kelganmi tekshirish
    existing = find_user(chat_id)

    if existing:
        # Mavjud mijoz — to'g'ridan-to'g'ri menyu
        name = existing[1] if len(existing) > 1 and existing[1] else "mijoz"
        bot.send_message(
            chat_id,
            f"Assalomu alaykum, {name}! 😊\n\nQuyidagi tugmalardan birini tanlang 👇",
            reply_markup=main_menu_keyboard()
        )
    else:
        # Yangi mijoz — ism so'raymiz
        user_data[chat_id] = {"step": "name"}
        bot.send_message(
            chat_id,
            "🛒 Assalomu alaykum!\n"
            "Sharq Supermarket rasmiy botiga xush kelibsiz!\n\n"
            "Ro'yxatdan o'tish uchun ismingizni yozing:",
            reply_markup=types.ReplyKeyboardRemove()
        )

# ==================== ISM OLISH (yangi mijoz) ====================
@bot.message_handler(func=lambda m: m.chat.id in user_data and user_data[m.chat.id].get("step") == "name")
def get_name(message):
    chat_id = message.chat.id
    user_data[chat_id]["name"] = message.text
    user_data[chat_id]["step"] = "phone"

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📞 Raqamni yuborish", request_contact=True)
    markup.add(btn)

    bot.send_message(chat_id, "Telefon raqamingizni yuboring:", reply_markup=markup)

# ==================== TELEFON OLISH ====================
@bot.message_handler(content_types=['contact'])
def get_phone(message):
    chat_id = message.chat.id

    if chat_id not in user_data:
        return

    phone = message.contact.phone_number.replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    # Telefon bo'yicha tekshirish
    existing = find_user(chat_id, phone)

    if existing:
        bot.send_message(
            chat_id,
            "Siz allaqachon ro'yxatdan o'tgansiz 🙏\n"
            "Chegirmangiz faol. Menyuga o'ting:",
            reply_markup=main_menu_keyboard()
        )
        user_data.pop(chat_id, None)
        return

    # Yangi mijoz — saqlash
    user_data[chat_id]["phone"] = phone
    name = user_data[chat_id].get("name", "")

    # Google Sheets'ga yozish (mavjud ustunlar tartibi bo'yicha):
    # user_id | name | phone | branch | rating | reason | problems | suggestions | low_rating_comment | date | sentiment | issue | root_cause
    try:
        sheet.append_row([
            chat_id,                                        # user_id
            name,                                           # name
            phone,                                          # phone
            "",                                             # branch
            "",                                             # rating
            "Ro'yxatdan o'tish (2% chegirma)",             # reason
            "",                                             # problems
            "",                                             # suggestions
            "",                                             # low_rating_comment
            datetime.now().strftime("%Y-%m-%d %H:%M"),     # date
            "",                                             # sentiment
            "",                                             # issue
            ""                                              # root_cause
        ])
    except Exception as e:
        print("Save error:", e)

    # Chegirma xabari
    bot.send_message(
        chat_id,
        f"🎁 Tabriklaymiz, {name}!\n"
        f"Sizga 2% chegirma berildi ✅\n\n"
        f"Endi quyidagi imkoniyatlardan foydalanishingiz mumkin 👇",
        reply_markup=main_menu_keyboard()
    )

    user_data.pop(chat_id, None)

# ==================== ASOSIY MENYU TUGMALARI ====================
@bot.message_handler(func=lambda m: m.text == "🎁 Chegirmani tekshirish")
def check_discount(message):
    chat_id = message.chat.id
    existing = find_user(chat_id)

    if existing:
        name = existing[1] if len(existing) > 1 else ""
        phone = existing[2] if len(existing) > 2 else ""
        date = existing[9] if len(existing) > 9 else ""
        bot.send_message(
            chat_id,
            f"✅ Sizning ma'lumotlaringiz:\n\n"
            f"👤 Ism: {name}\n"
            f"📞 Telefon: {phone}\n"
            f"🎁 Chegirma: 2%\n"
            f"📅 Ro'yxatdan o'tgan sana: {date}\n\n"
            f"Siz chegirmadan foydalanib bo'lgansiz.\n"
            f"Iltimos, supermarketimiz haqidagi fikrlaringizni qoldiring. "
            f"Sizning fikringiz biz uchun muhim 🙏",
            reply_markup=main_menu_keyboard()
        )
    else:
        bot.send_message(
            chat_id,
            "Siz hali ro'yxatdan o'tmagansiz.\n"
            "Chegirma olish uchun /start bosing va ro'yxatdan o'ting 🎁",
            reply_markup=main_menu_keyboard()
        )

@bot.message_handler(func=lambda m: m.text == "📷 Instagram")
def instagram_link(message):
    bot.send_message(
        message.chat.id,
        f"📷 Bizning Instagram sahifamiz:\n{INSTAGRAM_LINK}\n\n"
        f"Obuna bo'ling va yangi aksiyalardan xabardor bo'ling! 🔔",
        reply_markup=main_menu_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "📢 Telegram kanal")
def telegram_link(message):
    bot.send_message(
        message.chat.id,
        f"📢 Bizning Telegram kanalimiz:\n{TELEGRAM_LINK}\n\n"
        f"Obuna bo'ling va yangiliklardan xabardor bo'ling! 🔔",
        reply_markup=main_menu_keyboard()
    )

# ==================== FIKR QOLDIRISH ====================
@bot.message_handler(func=lambda m: m.text == "💬 Fikr qoldirish")
def start_feedback(message):
    chat_id = message.chat.id

    # Mijoz ma'lumotlarini olish
    existing = find_user(chat_id)
    if existing:
        name = existing[1] if len(existing) > 1 else ""
        phone = existing[2] if len(existing) > 2 else ""
    else:
        name = ""
        phone = ""

    feedback_data[chat_id] = {
        "name": name,
        "phone": phone,
        "step": "branch"
    }

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Haqqulobod", "To'rtko'l")
    bot.send_message(
        chat_id,
        "Qaysi filialdan foydalandingiz?",
        reply_markup=markup
    )

# Filial
@bot.message_handler(func=lambda m: m.chat.id in feedback_data and feedback_data[m.chat.id].get("step") == "branch")
def feedback_branch(message):
    chat_id = message.chat.id
    feedback_data[chat_id]["branch"] = message.text
    feedback_data[chat_id]["step"] = "like"

    bot.send_message(
        chat_id,
        "1️⃣ Supermarketimizning qaysi tomoni sizga yoqadi?\n"
        "(Quyidagilardan birini tanlang)",
        reply_markup=options_keyboard(LIKE_OPTIONS)
    )

# 1-savol: yoqqan tomoni (reason ustuniga yoziladi)
@bot.message_handler(func=lambda m: m.chat.id in feedback_data and feedback_data[m.chat.id].get("step") == "like")
def feedback_like(message):
    chat_id = message.chat.id
    text = message.text

    if text == "✍️ Boshqa (yozish)":
        feedback_data[chat_id]["step"] = "like_custom"
        bot.send_message(
            chat_id,
            "O'z fikringizni yozing:",
            reply_markup=types.ReplyKeyboardRemove()
        )
    elif text in LIKE_OPTIONS:
        feedback_data[chat_id]["reason"] = text
        feedback_data[chat_id]["step"] = "dislike"
        bot.send_message(
            chat_id,
            "2️⃣ Nima sizga yoqmadi yoki yaxshilanishi kerak?\n"
            "(Quyidagilardan birini tanlang)",
            reply_markup=options_keyboard(DISLIKE_OPTIONS)
        )
    else:
        bot.send_message(chat_id, "Iltimos, quyidagi variantlardan birini tanlang 👇")

@bot.message_handler(func=lambda m: m.chat.id in feedback_data and feedback_data[m.chat.id].get("step") == "like_custom")
def feedback_like_custom(message):
    chat_id = message.chat.id
    feedback_data[chat_id]["reason"] = f"Boshqa: {message.text}"
    feedback_data[chat_id]["step"] = "dislike"
    bot.send_message(
        chat_id,
        "Rahmat! 🙏\n\n"
        "2️⃣ Nima sizga yoqmadi yoki yaxshilanishi kerak?\n"
        "(Quyidagilardan birini tanlang)",
        reply_markup=options_keyboard(DISLIKE_OPTIONS)
    )

# 2-savol: yoqmagan tomoni (problems ustuniga yoziladi)
@bot.message_handler(func=lambda m: m.chat.id in feedback_data and feedback_data[m.chat.id].get("step") == "dislike")
def feedback_dislike(message):
    chat_id = message.chat.id
    text = message.text

    if text == "✍️ Boshqa (yozish)":
        feedback_data[chat_id]["step"] = "dislike_custom"
        bot.send_message(
            chat_id,
            "O'z fikringizni yozing:",
            reply_markup=types.ReplyKeyboardRemove()
        )
    elif text in DISLIKE_OPTIONS:
        feedback_data[chat_id]["problems"] = text
        feedback_data[chat_id]["step"] = "wish"
        bot.send_message(
            chat_id,
            "3️⃣ Qanday yangi xizmat yoki imkoniyatlar qo'shishimizni hohlaysiz?\n"
            "(Quyidagilardan birini tanlang)",
            reply_markup=options_keyboard(WISH_OPTIONS)
        )
    else:
        bot.send_message(chat_id, "Iltimos, quyidagi variantlardan birini tanlang 👇")

@bot.message_handler(func=lambda m: m.chat.id in feedback_data and feedback_data[m.chat.id].get("step") == "dislike_custom")
def feedback_dislike_custom(message):
    chat_id = message.chat.id
    feedback_data[chat_id]["problems"] = f"Boshqa: {message.text}"
    feedback_data[chat_id]["step"] = "wish"
    bot.send_message(
        chat_id,
        "Rahmat! 🙏\n\n"
        "3️⃣ Qanday yangi xizmat yoki imkoniyatlar qo'shishimizni hohlaysiz?\n"
        "(Quyidagilardan birini tanlang)",
        reply_markup=options_keyboard(WISH_OPTIONS)
    )

# 3-savol: istak (suggestions ustuniga yoziladi)
@bot.message_handler(func=lambda m: m.chat.id in feedback_data and feedback_data[m.chat.id].get("step") == "wish")
def feedback_wish(message):
    chat_id = message.chat.id
    text = message.text

    if text == "✍️ Boshqa (yozish)":
        feedback_data[chat_id]["step"] = "wish_custom"
        bot.send_message(
            chat_id,
            "O'z fikringizni yozing:",
            reply_markup=types.ReplyKeyboardRemove()
        )
    elif text in WISH_OPTIONS:
        feedback_data[chat_id]["suggestions"] = text
        ask_rating(chat_id)
    else:
        bot.send_message(chat_id, "Iltimos, quyidagi variantlardan birini tanlang 👇")

@bot.message_handler(func=lambda m: m.chat.id in feedback_data and feedback_data[m.chat.id].get("step") == "wish_custom")
def feedback_wish_custom(message):
    chat_id = message.chat.id
    feedback_data[chat_id]["suggestions"] = f"Boshqa: {message.text}"
    ask_rating(chat_id)

def ask_rating(chat_id):
    """Baholash so'raladi"""
    feedback_data[chat_id]["step"] = "rating"
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = [types.InlineKeyboardButton(f"⭐ {j}", callback_data=f"rate_{j}") for j in range(1, 6)]
    markup.add(*buttons)
    bot.send_message(
        chat_id,
        "Rahmat! 🙏\n\nEndi xizmatimizni baholang:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.send_message(chat_id, "Baho bering 👇", reply_markup=markup)

# Baholash
@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def get_rating(call):
    chat_id = call.message.chat.id
    if chat_id not in feedback_data:
        bot.answer_callback_query(call.id, "Qayta boshlang: /start")
        return

    rating = int(call.data.split("_")[1])
    feedback_data[chat_id]["rating"] = rating

    bot.answer_callback_query(call.id, f"Siz {rating} yulduz berdingiz")

    if rating <= 2:
        feedback_data[chat_id]["step"] = "low_rating"
        bot.send_message(
            chat_id,
            "❗ Siz past baho berdingiz.\n"
            "Iltimos, muammoni batafsil yozing — biz albatta yaxshilaymiz 🙏"
        )
    else:
        feedback_data[chat_id]["low_rating_comment"] = ""
        save_feedback(chat_id)

@bot.message_handler(func=lambda m: m.chat.id in feedback_data and feedback_data[m.chat.id].get("step") == "low_rating")
def get_low_rating_comment(message):
    chat_id = message.chat.id
    feedback_data[chat_id]["low_rating_comment"] = message.text
    save_feedback(chat_id)

def save_feedback(chat_id):
    """Fikrlarni Google Sheets'ga saqlash (mavjud ustunlar tartibi bo'yicha)"""
    data = feedback_data[chat_id]

    # user_id | name | phone | branch | rating | reason | problems | suggestions | low_rating_comment | date | sentiment | issue | root_cause
    try:
        sheet.append_row([
            chat_id,                                        # user_id
            data.get("name", ""),                           # name
            data.get("phone", ""),                          # phone
            data.get("branch", ""),                         # branch
            data.get("rating", ""),                         # rating
            data.get("reason", ""),                         # reason (yoqqan tomoni)
            data.get("problems", ""),                       # problems (yoqmagan tomoni)
            data.get("suggestions", ""),                    # suggestions (istak)
            data.get("low_rating_comment", ""),             # low_rating_comment
            datetime.now().strftime("%Y-%m-%d %H:%M"),     # date
            "",                                             # sentiment (AI uchun bo'sh)
            "",                                             # issue (AI uchun bo'sh)
            ""                                              # root_cause (AI uchun bo'sh)
        ])
    except Exception as e:
        print("Feedback save error:", e)

    bot.send_message(
        chat_id,
        "✅ Rahmat! Sizning fikringiz biz uchun juda muhim 🙏\n"
        "Har bir fikr — bizning rivojlanishimiz uchun muhim qadam.\n\n"
        "Xaridingiz uchun rahmat! 🛒",
        reply_markup=main_menu_keyboard()
    )

    feedback_data.pop(chat_id, None)

# ==================== WEBHOOK ====================
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Bot ishlayapti!"

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url="https://feedback-bot-saru.onrender.com/" + TOKEN)
    app.run(host="0.0.0.0", port=10000)
