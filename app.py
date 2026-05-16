import telebot
from flask import Flask, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from telebot import types
import os
import json
import time

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

BRANCH_LINKS = {
    "Haqqulobod": {
        "telegram": "https://t.me/sharqsupermarketi",
        "instagram": "https://instagram.com/sharq.supermarketi"
    },
    "To'rtko'l": {
        "telegram": "https://t.me/sharq_marketi",
        "instagram": "https://instagram.com/sharq_supermarketi"
    }
}

# ==================== ADMIN ====================
ADMIN_ID = 8008645253

# ==================== DATA ====================
user_data = {}
feedback_data = {}
broadcast_data = {}

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
    "🤝 Nasiya savdo",
    "🏪 Yangi filiallar ochilishi",
    "💳 Qulay to'lov turlari (Payme, Click)",
    "✍️ Boshqa (yozish)"
]

# ==================== YORDAMCHI FUNKSIYALAR ====================
def main_menu_keyboard():
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

def multi_select_keyboard(options, selected=None):
    """Ko'p javob tanlash uchun inline klaviatura"""
    if selected is None:
        selected = []
    markup = types.InlineKeyboardMarkup(row_width=1)
    for opt in options:
        if opt == "✍️ Boshqa (yozish)":
            markup.add(types.InlineKeyboardButton(opt, callback_data=f"ms_custom"))
        else:
            check = "✅ " if opt in selected else ""
            markup.add(types.InlineKeyboardButton(f"{check}{opt}", callback_data=f"ms_{opt}"))
    markup.add(types.InlineKeyboardButton("📨 Tayyor", callback_data="ms_done"))
    return markup

def find_user(chat_id, phone=None):
    try:
        all_records = sheet.get_all_values()
        for row in all_records[1:]:
            if len(row) > 0 and str(row[0]) == str(chat_id):
                return row
            if phone and len(row) > 2 and row[2] and row[2].replace(" ", "") == phone.replace(" ", ""):
                return row
        return None
    except Exception as e:
        print("Find user error:", e)
        return None

def get_all_user_ids():
    try:
        all_records = sheet.get_all_values()
        ids = []
        seen = set()
        for row in all_records[1:]:
            if row and row[0] and row[0] not in seen:
                try:
                    ids.append(int(row[0]))
                    seen.add(row[0])
                except ValueError:
                    pass
        return ids
    except Exception as e:
        print("get_all_user_ids error:", e)
        return []

def is_admin(chat_id):
    return chat_id == ADMIN_ID

def ask_multi_select(chat_id, step):
    """Ko'p javob tanlash savolini yuborish"""
    if step == "like":
        text = "1️⃣ Supermarketimizning qaysi tomoni sizga yoqadi?\n_(Bir yoki bir nechta tanlang, keyin 📨 Tayyor bosing)_"
        options = LIKE_OPTIONS
    elif step == "dislike":
        text = "2️⃣ Nima sizga yoqmadi yoki yaxshilanishi kerak?\n_(Bir yoki bir nechta tanlang, keyin 📨 Tayyor bosing)_"
        options = DISLIKE_OPTIONS
    else:
        text = "3️⃣ Qanday yangi xizmat yoki imkoniyatlar qo'shishimizni hohlaysiz?\n_(Bir yoki bir nechta tanlang, keyin 📨 Tayyor bosing)_"
        options = WISH_OPTIONS

    feedback_data[chat_id]["step"] = step
    feedback_data[chat_id][f"{step}_selected"] = []

    bot.send_message(
        chat_id,
        text,
        parse_mode="Markdown",
        reply_markup=multi_select_keyboard(options, [])
    )

# ==================== START ====================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_data.pop(chat_id, None)
    feedback_data.pop(chat_id, None)

    existing = find_user(chat_id)

    if existing:
        name = existing[1] if len(existing) > 1 and existing[1] else "mijoz"
        bot.send_message(
            chat_id,
            f"Assalomu alaykum, {name}! 😊\n\nQuyidagi tugmalardan birini tanlang 👇",
            reply_markup=main_menu_keyboard()
        )
    else:
        user_data[chat_id] = {"step": "name"}
        bot.send_message(
            chat_id,
            "🛒 Assalomu alaykum!\n"
            "Sharq Supermarket rasmiy botiga xush kelibsiz!\n\n"
            "Ro'yxatdan o'tish uchun ismingizni yozing:",
            reply_markup=types.ReplyKeyboardRemove()
        )

# ==================== ISM OLISH ====================
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

    user_data[chat_id]["phone"] = phone
    name = user_data[chat_id].get("name", "")

    try:
        sheet.append_row([
            chat_id, name, phone, "", "",
            "Ro'yxatdan o'tish (2% chegirma)",
            "", "", "",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "", "", ""
        ])
    except Exception as e:
        print("Save error:", e)

    bot.send_message(
        chat_id,
        f"🎁 Tabriklaymiz, {name}!\n"
        f"Sizga 2% chegirma berildi ✅\n\n"
        f"Endi quyidagi imkoniyatlardan foydalanishingiz mumkin 👇",
        reply_markup=main_menu_keyboard()
    )
    user_data.pop(chat_id, None)

# ==================== ASOSIY MENYU ====================
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

    existing = find_user(chat_id)
    name = existing[1] if existing and len(existing) > 1 else ""
    phone = existing[2] if existing and len(existing) > 2 else ""

    feedback_data[chat_id] = {"name": name, "phone": phone, "step": "branch"}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Haqqulobod", "To'rtko'l")
    bot.send_message(chat_id, "Qaysi filialdan foydalandingiz?", reply_markup=markup)

# Filial tanlash
@bot.message_handler(func=lambda m: m.chat.id in feedback_data and feedback_data[m.chat.id].get("step") == "branch")
def feedback_branch(message):
    chat_id = message.chat.id
    branch = message.text
    feedback_data[chat_id]["branch"] = branch
    feedback_data[chat_id]["step"] = "like"

    links = BRANCH_LINKS.get(branch)
    if links:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📢 Telegram kanal", url=links["telegram"]),
            types.InlineKeyboardButton("📷 Instagram", url=links["instagram"])
        )
        bot.send_message(
            chat_id,
            f"📍 *{branch}* filiali ijtimoiy tarmoqlari:",
            parse_mode="Markdown",
            reply_markup=markup
        )

    ask_multi_select(chat_id, "like")

# ==================== KO'P JAVOB TANLASH (CALLBACK) ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("ms_"))
def multi_select_handler(call):
    chat_id = call.message.chat.id

    if chat_id not in feedback_data:
        bot.answer_callback_query(call.id, "Qayta boshlang: /start")
        return

    step = feedback_data[chat_id].get("step")
    selected_key = f"{step}_selected"

    if call.data == "ms_done":
        selected = feedback_data[chat_id].get(selected_key, [])

        if not selected:
            bot.answer_callback_query(call.id, "⚠️ Kamida bitta tanlang!", show_alert=True)
            return

        bot.answer_callback_query(call.id)

        # Tanlangan javoblarni saqlash
        feedback_data[chat_id][step_to_field(step)] = ", ".join(selected)

        # Keyingi savolga o'tish
        if step == "like":
            ask_multi_select(chat_id, "dislike")
        elif step == "dislike":
            ask_multi_select(chat_id, "wish")
        elif step == "wish":
            ask_rating(chat_id)

    elif call.data == "ms_custom":
        bot.answer_callback_query(call.id)
        feedback_data[chat_id]["step"] = f"{step}_custom"
        bot.send_message(chat_id, "✍️ O'z fikringizni yozing:", reply_markup=types.ReplyKeyboardRemove())

    else:
        # Variant tanlash/bekor qilish
        option = call.data[3:]  # "ms_" ni olib tashlash
        selected = feedback_data[chat_id].get(selected_key, [])

        if option in selected:
            selected.remove(option)
        else:
            selected.append(option)

        feedback_data[chat_id][selected_key] = selected

        # Mos options ro'yxatini aniqlash
        if step == "like":
            options = LIKE_OPTIONS
        elif step == "dislike":
            options = DISLIKE_OPTIONS
        else:
            options = WISH_OPTIONS

        # Tugmalarni yangilash
        try:
            bot.edit_message_reply_markup(
                chat_id,
                call.message.message_id,
                reply_markup=multi_select_keyboard(options, selected)
            )
        except Exception as e:
            print("Edit markup error:", e)

        bot.answer_callback_query(call.id)

def step_to_field(step):
    mapping = {"like": "reason", "dislike": "problems", "wish": "suggestions"}
    return mapping.get(step, step)

# Boshqa (yozish) — matn qabul qilish
@bot.message_handler(func=lambda m: m.chat.id in feedback_data and feedback_data[m.chat.id].get("step", "").endswith("_custom"))
def handle_custom_text(message):
    chat_id = message.chat.id
    step = feedback_data[chat_id]["step"].replace("_custom", "")
    selected_key = f"{step}_selected"

    # Mavjud tanlovlarga qo'shish
    selected = feedback_data[chat_id].get(selected_key, [])
    selected.append(f"Boshqa: {message.text}")
    feedback_data[chat_id][step_to_field(step)] = ", ".join(selected)

    bot.send_message(chat_id, "✅ Qabul qilindi! 🙏")

    if step == "like":
        ask_multi_select(chat_id, "dislike")
    elif step == "dislike":
        ask_multi_select(chat_id, "wish")
    elif step == "wish":
        ask_rating(chat_id)

# ==================== BAHOLASH ====================
def ask_rating(chat_id):
    feedback_data[chat_id]["step"] = "rating"
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = [types.InlineKeyboardButton(f"⭐ {j}", callback_data=f"rate_{j}") for j in range(1, 6)]
    markup.add(*buttons)
    bot.send_message(chat_id, "Rahmat! 🙏\n\nEndi xizmatimizni baholang:", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(chat_id, "Baho bering 👇", reply_markup=markup)

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
    data = feedback_data[chat_id]
    try:
        sheet.append_row([
            chat_id,
            data.get("name", ""),
            data.get("phone", ""),
            data.get("branch", ""),
            data.get("rating", ""),
            data.get("reason", ""),
            data.get("problems", ""),
            data.get("suggestions", ""),
            data.get("low_rating_comment", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "", "", ""
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


# ==================== BROADCAST ====================
@bot.message_handler(commands=['broadcast'])
def broadcast_start(message):
    chat_id = message.chat.id
    if not is_admin(chat_id):
        bot.send_message(chat_id, "❌ Bu buyruq faqat admin uchun!")
        return

    broadcast_data[chat_id] = {"step": "type"}

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📝 Faqat matn", callback_data="bc_type_text"),
        types.InlineKeyboardButton("🖼 Rasm + matn", callback_data="bc_type_photo")
    )
    bot.send_message(
        chat_id,
        "📢 *Broadcast xabari*\n\nQanday formatda yuborasiz?",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("bc_type_"))
def broadcast_type(call):
    chat_id = call.message.chat.id
    if not is_admin(chat_id):
        return

    msg_type = call.data.replace("bc_type_", "")
    broadcast_data[chat_id]["type"] = msg_type
    bot.answer_callback_query(call.id)

    if msg_type == "photo":
        broadcast_data[chat_id]["step"] = "photo"
        bot.send_message(chat_id, "🖼 Rasmni yuboring:", reply_markup=types.ReplyKeyboardRemove())
    else:
        broadcast_data[chat_id]["step"] = "text"
        bot.send_message(chat_id, "📝 Xabar matnini yozing:", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(
    content_types=['photo'],
    func=lambda m: m.chat.id in broadcast_data and broadcast_data[m.chat.id].get("step") == "photo"
)
def broadcast_get_photo(message):
    chat_id = message.chat.id
    broadcast_data[chat_id]["photo_id"] = message.photo[-1].file_id
    broadcast_data[chat_id]["step"] = "text"
    bot.send_message(chat_id, "✅ Rasm qabul qilindi!\n\nEndi xabar matnini yozing (caption):")

@bot.message_handler(
    func=lambda m: m.chat.id in broadcast_data and broadcast_data[m.chat.id].get("step") == "text"
)
def broadcast_get_text(message):
    chat_id = message.chat.id
    broadcast_data[chat_id]["text"] = message.text
    broadcast_data[chat_id]["step"] = "confirm"

    bc = broadcast_data[chat_id]
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Yuborish", callback_data="bc_confirm_yes"),
        types.InlineKeyboardButton("❌ Bekor qilish", callback_data="bc_confirm_no")
    )

    if bc.get("photo_id"):
        bot.send_photo(chat_id, bc["photo_id"], caption=f"👁 Preview:\n\n{message.text}", reply_markup=markup)
    else:
        bot.send_message(chat_id, f"👁 *Preview:*\n\n{message.text}", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("bc_confirm_"))
def broadcast_confirm(call):
    chat_id = call.message.chat.id
    if not is_admin(chat_id):
        return

    bot.answer_callback_query(call.id)

    if call.data == "bc_confirm_no":
        broadcast_data.pop(chat_id, None)
        bot.send_message(chat_id, "❌ Broadcast bekor qilindi.", reply_markup=main_menu_keyboard())
        return

    bc = broadcast_data.get(chat_id, {})
    text = bc.get("text", "")
    photo_id = bc.get("photo_id")

    user_ids = get_all_user_ids()
    total = len(user_ids)

    if total == 0:
        bot.send_message(chat_id, "⚠️ Foydalanuvchilar topilmadi!")
        broadcast_data.pop(chat_id, None)
        return

    status_msg = bot.send_message(chat_id, f"📤 Yuborilmoqda... (0/{total})")
    success = 0
    failed = 0

    for i, uid in enumerate(user_ids):
        try:
            if photo_id:
                bot.send_photo(uid, photo_id, caption=text)
            else:
                bot.send_message(uid, text)
            success += 1
        except Exception as e:
            print(f"Broadcast error uid={uid}: {e}")
            failed += 1

        if (i + 1) % 10 == 0:
            try:
                bot.edit_message_text(f"📤 Yuborilmoqda... ({i+1}/{total})", chat_id, status_msg.message_id)
            except:
                pass

        time.sleep(0.05)

    bot.edit_message_text(
        f"✅ *Broadcast yakunlandi!*\n\n"
        f"👥 Jami: {total}\n"
        f"✅ Yuborildi: {success}\n"
        f"❌ Xato: {failed}",
        chat_id,
        status_msg.message_id,
        parse_mode="Markdown"
    )
    broadcast_data.pop(chat_id, None)


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
