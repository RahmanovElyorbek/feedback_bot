import telebot
from flask import Flask, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from telebot import types
import os
import json
import time
import openai
import base64
import re

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
spreadsheet = client.open_by_key("1ghegwU8QA-JiARIMuFyiBAHyZGDw2238krqNhukzCrU")
sheet = spreadsheet.sheet1

# ==================== AKSIYA: SHEETS VA OPENAI ====================
def get_or_create_worksheet(name, headers):
    try:
        return spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers))
        ws.append_row(headers)
        return ws

aksiya_cheklar_sheet = get_or_create_worksheet(
    "aksiya_cheklar",
    ["tiraj_id", "user_id", "ism", "telefon", "chek_raqami", "summa", "rasm_fayl_id", "sana", "holat"]
)
aksiya_tirajlar_sheet = get_or_create_worksheet(
    "aksiya_tirajlar",
    ["tiraj_id", "boshlanish", "tugash", "jami_chek", "jami_summa", "goliblar_soni", "holat"]
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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
aksiya_data = {}
aksiya_finish_data = {}

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
def main_menu_keyboard(chat_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("👤 Mening ma'lumotlarim"),
        types.KeyboardButton("💬 Fikr qoldirish")
    )
    markup.add(
        types.KeyboardButton("📷 Instagram"),
        types.KeyboardButton("📢 Telegram kanal")
    )
    markup.add(types.KeyboardButton("🎰 Aksiyaga qatnashish"))
    if chat_id is not None and is_admin(chat_id):
        markup.add(types.KeyboardButton("📊 Aksiya xulosasi"))
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

# ==================== AKSIYA: YORDAMCHI FUNKSIYALAR ====================
def create_new_tiraj():
    """Yangi tiraj yaratish va uni faol deb belgilash"""
    try:
        records = aksiya_tirajlar_sheet.get_all_values()
        existing_ids = [int(row[0]) for row in records[1:] if row and row[0].isdigit()]
        new_id = max(existing_ids) + 1 if existing_ids else 1
        row = [new_id, datetime.now().strftime("%Y-%m-%d %H:%M"), "", 0, 0, 0, "faol"]
        aksiya_tirajlar_sheet.append_row(row)
        return row
    except Exception as e:
        print("create_new_tiraj error:", e)
        return None

def get_active_tiraj():
    """Faol tirajni topish, agar yo'q bo'lsa yangisini yaratish"""
    try:
        records = aksiya_tirajlar_sheet.get_all_values()
        for row in records[1:]:
            if len(row) > 6 and row[6] == "faol":
                return row
        return create_new_tiraj()
    except Exception as e:
        print("get_active_tiraj error:", e)
        return None

def get_tiraj_checks(tiraj_id):
    """Berilgan tirajga tegishli barcha cheklarni qaytarish"""
    try:
        records = aksiya_cheklar_sheet.get_all_values()
        return [row for row in records[1:] if row and str(row[0]) == str(tiraj_id)]
    except Exception as e:
        print("get_tiraj_checks error:", e)
        return []

def find_check_by_number(tiraj_id, chek_raqami):
    """Shu tirajda chek raqami avval yuborilganmi tekshirish"""
    for row in get_tiraj_checks(tiraj_id):
        if len(row) > 4 and row[4] == str(chek_raqami):
            return row
    return None

def save_check(tiraj_id, user_id, ism, telefon, chek_raqami, summa, file_id):
    try:
        aksiya_cheklar_sheet.append_row([
            tiraj_id, user_id, ism, telefon, chek_raqami, summa, file_id,
            datetime.now().strftime("%Y-%m-%d %H:%M"), "faol"
        ])
    except Exception as e:
        print("save_check error:", e)

def mark_winning_checks(tiraj_id, chek_raqami_set):
    try:
        records = aksiya_cheklar_sheet.get_all_values()
        for idx, row in enumerate(records[1:], start=2):
            if row and str(row[0]) == str(tiraj_id) and len(row) > 4 and row[4] in chek_raqami_set:
                aksiya_cheklar_sheet.update_cell(idx, 9, "g'olib")
    except Exception as e:
        print("mark_winning_checks error:", e)

def close_tiraj(tiraj_id, jami_chek, jami_summa, goliblar_soni):
    try:
        records = aksiya_tirajlar_sheet.get_all_values()
        for idx, row in enumerate(records[1:], start=2):
            if row and str(row[0]) == str(tiraj_id):
                aksiya_tirajlar_sheet.update(f"A{idx}:G{idx}", [[
                    row[0], row[1], datetime.now().strftime("%Y-%m-%d %H:%M"),
                    jami_chek, jami_summa, goliblar_soni, "yakunlangan"
                ]])
                break
    except Exception as e:
        print("close_tiraj error:", e)

def read_check_image(file_bytes):
    """Chek rasmidan chek raqami va summani GPT-4o Vision orqali o'qish"""
    try:
        base64_image = base64.b64encode(file_bytes).decode('utf-8')
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        },
                        {
                            "type": "text",
                            "text": (
                                "Bu o'zbek supermarket cheki. Faqat JSON formatda javob ber, "
                                "boshqa hech narsa yozma:\n"
                                "{\n"
                                '  "chek_raqami": "chekdagi tartib raqami (faqat raqamlar)",\n'
                                '  "summa": 150000\n'
                                "}\n"
                                "Agar chek raqami yoki summa aniqlanmasa — null yoz."
                            )
                        }
                    ]
                }
            ],
            max_tokens=100
        )
        content = response.choices[0].message.content.strip()
        content = re.sub(r"^```(json)?|```$", "", content).strip()
        return json.loads(content)
    except Exception as e:
        print("read_check_image error:", e)
        return None

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
            reply_markup=main_menu_keyboard(chat_id)
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
            "Menyuga o'ting:",
            reply_markup=main_menu_keyboard(chat_id)
        )
        user_data.pop(chat_id, None)
        return

    user_data[chat_id]["phone"] = phone
    name = user_data[chat_id].get("name", "")

    try:
        sheet.append_row([
            chat_id, name, phone, "", "",
            "Ro'yxatdan o'tish",
            "", "", "",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "", "", ""
        ])
    except Exception as e:
        print("Save error:", e)

    bot.send_message(
        chat_id,
        f"✅ Tabriklaymiz, {name}!\n"
        f"Siz muvaffaqiyatli ro'yxatdan o'tdingiz.\n\n"
        f"Quyidagi imkoniyatlardan foydalanishingiz mumkin 👇",
        reply_markup=main_menu_keyboard(chat_id)
    )
    user_data.pop(chat_id, None)

# ==================== ASOSIY MENYU ====================
@bot.message_handler(func=lambda m: m.text == "👤 Mening ma'lumotlarim")
def my_info(message):
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
            f"📅 Ro'yxatdan o'tgan sana: {date}\n\n"
            f"Iltimos, supermarketimiz haqidagi fikrlaringizni qoldiring. "
            f"Sizning fikringiz biz uchun muhim 🙏",
            reply_markup=main_menu_keyboard(chat_id)
        )
    else:
        bot.send_message(
            chat_id,
            "Siz hali ro'yxatdan o'tmagansiz.\n"
            "Ro'yxatdan o'tish uchun /start bosing 🙏",
            reply_markup=main_menu_keyboard(chat_id)
        )

@bot.message_handler(func=lambda m: m.text == "📷 Instagram")
def instagram_link(message):
    chat_id = message.chat.id
    bot.send_message(
        chat_id,
        f"📷 Bizning Instagram sahifamiz:\n{INSTAGRAM_LINK}\n\n"
        f"Obuna bo'ling va yangi aksiyalardan xabardor bo'ling! 🔔",
        reply_markup=main_menu_keyboard(chat_id)
    )

@bot.message_handler(func=lambda m: m.text == "📢 Telegram kanal")
def telegram_link(message):
    chat_id = message.chat.id
    bot.send_message(
        chat_id,
        f"📢 Bizning Telegram kanalimiz:\n{TELEGRAM_LINK}\n\n"
        f"Obuna bo'ling va yangiliklardan xabardor bo'ling! 🔔",
        reply_markup=main_menu_keyboard(chat_id)
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
        reply_markup=main_menu_keyboard(chat_id)
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
        bot.send_message(chat_id, "❌ Broadcast bekor qilindi.", reply_markup=main_menu_keyboard(chat_id))
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


# ==================== AKSIYA MODULI ====================
@bot.message_handler(func=lambda m: m.text == "🎰 Aksiyaga qatnashish")
def aksiya_start(message):
    chat_id = message.chat.id

    if not openai_client:
        bot.send_message(
            chat_id,
            "⚠️ Aksiya moduli hozircha ishlamayapti. Keyinroq urinib ko'ring.",
            reply_markup=main_menu_keyboard(chat_id)
        )
        return

    aksiya_data[chat_id] = {"step": "aksiya_photo"}
    bot.send_message(
        chat_id,
        "🎰 Aksiyaga qatnashish uchun chek rasmini yuboring.\n"
        "❗️ Chekda ismingiz va telefon raqamingiz yozilgan bo'lishi shart.",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(
    content_types=['photo'],
    func=lambda m: m.chat.id in aksiya_data and aksiya_data[m.chat.id].get("step") == "aksiya_photo"
)
def aksiya_get_photo(message):
    chat_id = message.chat.id

    if not openai_client:
        bot.send_message(
            chat_id,
            "⚠️ Aksiya moduli hozircha ishlamayapti. Keyinroq urinib ko'ring.",
            reply_markup=main_menu_keyboard(chat_id)
        )
        aksiya_data.pop(chat_id, None)
        return

    bot.send_message(chat_id, "⏳ Chek tekshirilmoqda...")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        file_bytes = bot.download_file(file_info.file_path)
    except Exception as e:
        print("Aksiya rasm yuklab olish xatosi:", e)
        bot.send_message(
            chat_id,
            "❌ Rasmni yuklab bo'lmadi. Qaytadan urinib ko'ring.",
            reply_markup=main_menu_keyboard(chat_id)
        )
        aksiya_data.pop(chat_id, None)
        return

    result = read_check_image(file_bytes)

    if not result or (not result.get("chek_raqami") and result.get("summa") is None):
        bot.send_message(chat_id, "❌ Rasm chek emas. Iltimos, chek rasmini yuboring")
        return

    chek_raqami = result.get("chek_raqami")
    summa = result.get("summa")

    if not chek_raqami:
        bot.send_message(chat_id, "⚠️ Chek raqami aniqlanmadi. Rasmni aniqroq olib, qayta yuboring")
        return

    try:
        summa = int(summa)
    except (TypeError, ValueError):
        bot.send_message(chat_id, "⚠️ Chek summasi aniqlanmadi. Rasmni aniqroq olib, qayta yuboring")
        return

    tiraj = get_active_tiraj()
    if not tiraj:
        bot.send_message(
            chat_id,
            "⚠️ Hozircha faol tiraj yo'q. Keyinroq urinib ko'ring.",
            reply_markup=main_menu_keyboard(chat_id)
        )
        aksiya_data.pop(chat_id, None)
        return

    tiraj_id = tiraj[0]

    if find_check_by_number(tiraj_id, chek_raqami):
        bot.send_message(
            chat_id,
            f"⚠️ Bu chek raqami allaqachon ro'yxatga olingan ({chek_raqami})",
            reply_markup=main_menu_keyboard(chat_id)
        )
        aksiya_data.pop(chat_id, None)
        return

    existing = find_user(chat_id)
    ism = existing[1] if existing and len(existing) > 1 and existing[1] else (message.from_user.first_name or "mijoz")
    telefon = existing[2] if existing and len(existing) > 2 and existing[2] else ""

    save_check(tiraj_id, chat_id, ism, telefon, chek_raqami, summa, message.photo[-1].file_id)

    bot.send_message(
        chat_id,
        f"✅ Tabriklaymiz, {ism}!\n"
        f"Chekingiz aksiyaga qabul qilindi 🎉\n\n"
        f"📋 Chek raqami: {chek_raqami}\n"
        f"💰 Summa: {summa:,} so'm\n"
        f"🎰 Tiraj: #{tiraj_id}\n\n"
        f"Tiraj kuni barcha ishtirokchilarga xabar yuboriladi.\n"
        f"Omad tilaymiz! 🍀",
        reply_markup=main_menu_keyboard(chat_id)
    )
    aksiya_data.pop(chat_id, None)

# ==================== AKSIYA: TIRAJNI YAKUNLASH (ADMIN) ====================
@bot.message_handler(commands=['aksiya_yakunla'])
def aksiya_finish_start(message):
    chat_id = message.chat.id
    if not is_admin(chat_id):
        bot.send_message(chat_id, "❌ Bu buyruq faqat admin uchun!")
        return

    tiraj = get_active_tiraj()
    if not tiraj:
        bot.send_message(chat_id, "⚠️ Faol tiraj topilmadi.")
        return

    tiraj_id = tiraj[0]
    cheklar = get_tiraj_checks(tiraj_id)

    if not cheklar:
        bot.send_message(chat_id, f"⚠️ Joriy tiraj #{tiraj_id} da hali chek yo'q.")
        return

    aksiya_finish_data[chat_id] = {"step": "numbers", "tiraj_id": tiraj_id}

    bot.send_message(
        chat_id,
        f"Joriy tiraj #{tiraj_id} da {len(cheklar)} ta chek bor.\n"
        f"G'olib chek raqamlarini yuboring (har birini yangi qatorda):\n\n"
        f"Misol:\n00123456\n00234567\n00345678",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(
    func=lambda m: m.chat.id in aksiya_finish_data and aksiya_finish_data[m.chat.id].get("step") == "numbers"
)
def aksiya_finish_numbers(message):
    chat_id = message.chat.id
    if not is_admin(chat_id):
        return

    tiraj_id = aksiya_finish_data[chat_id]["tiraj_id"]
    numbers = [n.strip() for n in message.text.splitlines() if n.strip()]

    if not numbers:
        bot.send_message(chat_id, "⚠️ Kamida bitta chek raqami yuboring.")
        return

    cheklar = get_tiraj_checks(tiraj_id)
    found = []
    not_found = []

    for num in numbers:
        match = next((row for row in cheklar if row[4] == num), None)
        if match:
            found.append(match)
        else:
            not_found.append(num)

    if not found:
        bot.send_message(
            chat_id,
            "⚠️ Hech qanday mos chek topilmadi. Qaytadan urinib ko'ring yoki /aksiya_yakunla bilan qayta boshlang."
        )
        aksiya_finish_data.pop(chat_id, None)
        return

    aksiya_finish_data[chat_id]["step"] = "confirm"
    aksiya_finish_data[chat_id]["winners"] = found

    lines = ["✅ Topildi:"]
    for row in found:
        lines.append(f"- #{row[4]} → {row[2]}")

    if not_found:
        lines.append("\n❌ Topilmadi:")
        for num in not_found:
            lines.append(f"- #{num} (bu raqam ro'yxatda yo'q)")

    lines.append("\nDavom ettirilsinmi?")

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ha", callback_data="aksiya_finish_yes"),
        types.InlineKeyboardButton("❌ Bekor qilish", callback_data="aksiya_finish_no")
    )
    bot.send_message(chat_id, "\n".join(lines), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("aksiya_finish_"))
def aksiya_finish_confirm(call):
    chat_id = call.message.chat.id
    if not is_admin(chat_id):
        return

    bot.answer_callback_query(call.id)

    if call.data == "aksiya_finish_no" or chat_id not in aksiya_finish_data:
        aksiya_finish_data.pop(chat_id, None)
        bot.send_message(chat_id, "❌ Bekor qilindi.", reply_markup=main_menu_keyboard(chat_id))
        return

    data = aksiya_finish_data[chat_id]
    tiraj_id = data["tiraj_id"]
    winners = data.get("winners", [])

    all_checks = get_tiraj_checks(tiraj_id)
    winner_chek_raqami = {row[4] for row in winners}
    winner_user_ids = {row[1] for row in winners}

    jami_chek = len(all_checks)
    jami_summa = sum(int(row[5]) for row in all_checks if len(row) > 5 and str(row[5]).isdigit())

    ism_by_user = {}
    for row in all_checks:
        ism_by_user.setdefault(row[1], row[2])
    non_winner_user_ids = {row[1] for row in all_checks if row[1] not in winner_user_ids}

    win_success, win_failed = 0, 0
    for row in winners:
        try:
            bot.send_message(
                int(row[1]),
                f"🏆 Tabriklaymiz, {row[2]}!\n"
                f"Siz Sharq Supermarket #{tiraj_id}-tiraj aksiyasida G'OLIB bo'ldingiz! 🎉\n\n"
                f"🎁 Sovg'angizni olish uchun supermarketimizga tashrif buyuring\n"
                f"va bu xabarni kassirga ko'rsating.\n\n"
                f"Sharq Supermarket jamoasi sizni kutadi! 🛒"
            )
            win_success += 1
        except Exception as e:
            print(f"Aksiya g'olib xabar error uid={row[1]}: {e}")
            win_failed += 1
        time.sleep(0.05)

    lose_success, lose_failed = 0, 0
    for uid in non_winner_user_ids:
        try:
            bot.send_message(
                int(uid),
                f"🎰 Sharq Supermarket #{tiraj_id}-tiraj aksiyasi yakunlandi.\n\n"
                f"Hurmatli {ism_by_user.get(uid, 'mijoz')}, bu safar omad kulib boqmadi 🍀\n"
                f"Lekin umid uzilmasin — keyingi tirajda siz g'olib bo'lishingiz mumkin!\n\n"
                f"Aksiyada qatnashganingiz uchun rahmat 🙏\n"
                f"Sharq Supermarket doimo sizni kutadi! 🛒"
            )
            lose_success += 1
        except Exception as e:
            print(f"Aksiya qatnashchi xabar error uid={uid}: {e}")
            lose_failed += 1
        time.sleep(0.05)

    close_tiraj(tiraj_id, jami_chek, jami_summa, len(winners))
    mark_winning_checks(tiraj_id, winner_chek_raqami)
    new_tiraj = create_new_tiraj()

    aksiya_finish_data.pop(chat_id, None)

    bot.send_message(
        chat_id,
        f"✅ *Tiraj #{tiraj_id} yakunlandi!*\n\n"
        f"👥 Jami chek: {jami_chek}\n"
        f"💰 Jami summa: {jami_summa:,} so'm\n"
        f"🏆 G'oliblar: {len(winners)}\n\n"
        f"📤 G'oliblarga yuborildi: {win_success}/{len(winners)}\n"
        f"📤 Qolganlarga yuborildi: {lose_success}/{len(non_winner_user_ids)}\n\n"
        f"🆕 Yangi tiraj #{new_tiraj[0]} boshlandi." if new_tiraj else f"⚠️ Yangi tiraj yaratilmadi, qo'lda tekshiring.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(chat_id)
    )

# ==================== AKSIYA XULOSASI (ADMIN) ====================
@bot.message_handler(func=lambda m: m.text == "📊 Aksiya xulosasi")
def aksiya_summary(message):
    chat_id = message.chat.id
    if not is_admin(chat_id):
        return

    try:
        tiraj_records = aksiya_tirajlar_sheet.get_all_values()[1:]
    except Exception as e:
        print("aksiya_summary error:", e)
        tiraj_records = []

    if not tiraj_records:
        bot.send_message(chat_id, "📊 Hali aksiya tirajlari yo'q.", reply_markup=main_menu_keyboard(chat_id))
        return

    current = next((r for r in tiraj_records if len(r) > 6 and r[6] == "faol"), None)
    current_id = current[0] if current else None

    checks = get_tiraj_checks(current_id) if current_id else []
    unique_users = {row[1] for row in checks}
    jami_summa_joriy = sum(int(row[5]) for row in checks if len(row) > 5 and str(row[5]).isdigit())

    lines = ["📊 *AKSIYA XULOSASI*", ""]

    if current:
        lines.append(f"🔄 Joriy tiraj: #{current_id}")
        lines.append(f"📅 Boshlangan: {current[1]}")
        lines.append(f"📋 Qatnashchilar: {len(checks)} ta chek ({len(unique_users)} ta mijoz)")
        lines.append(f"💰 Jami summa: {jami_summa_joriy:,} so'm")
        lines.append("")

    finished = [r for r in tiraj_records if len(r) > 6 and r[6] == "yakunlangan"]
    if finished and current:
        prev = finished[-1]
        prev_chek = int(prev[3]) if len(prev) > 3 and prev[3].isdigit() else 0
        prev_summa = int(prev[4]) if len(prev) > 4 and prev[4].isdigit() else 0
        chek_diff_pct = ((len(checks) - prev_chek) / prev_chek * 100) if prev_chek else 0
        summa_diff_pct = ((jami_summa_joriy - prev_summa) / prev_summa * 100) if prev_summa else 0
        lines.append(f"📈 O'tgan tiraj (#{prev[0]}) bilan taqqoslash:")
        lines.append(f"   Cheklar: {prev_chek} → {len(checks)} ({chek_diff_pct:+.0f}% o'zgarish)")
        lines.append(f"   Summa: {prev_summa:,} → {jami_summa_joriy:,} so'm ({summa_diff_pct:+.1f}% 📈)")
        lines.append("")

    lines.append("🏆 Barcha tirajlar:")
    for r in tiraj_records:
        tid = r[0]
        jc = r[3] if len(r) > 3 else "0"
        js = r[4] if len(r) > 4 else "0"
        try:
            js_fmt = f"{int(js):,}"
        except ValueError:
            js_fmt = js
        marker = " (joriy)" if current_id and tid == current_id else ""
        lines.append(f"   #{tid} → {jc} chek | {js_fmt} so'm{marker}")

    bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown", reply_markup=main_menu_keyboard(chat_id))


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
