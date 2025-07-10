import telebot
import json
import datetime
from telebot import types

bot = telebot.TeleBot("8104145335:AAFTbK1RPQ-6FKV3QCrmLN-r0hiuBi2T7yU")  # Replace with your real bot token

# Load premium users
try:
    with open("premium_users.json", "r") as f:
        premium_users = json.load(f)
except:
    premium_users = []

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('/english', '/bengali', '/hindi', '/mcq', '/notes', '/mocktest', '/premium')
    bot.send_message(message.chat.id, "👋 Welcome to NEETHelper24x7Bot!\nChoose your preferred language to begin.", reply_markup=markup)

@bot.message_handler(commands=['premium'])
def premium(message):
    qr = open("assets/qr.png", "rb")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Done", callback_data="paid_done"))
    bot.send_photo(message.chat.id, qr,
                   caption="🎓 Become a Premium Member!\n\n💠 Choose your plan:\n🔹 ₹49 – 30 days access\n🔸 ₹299 – Full NEET season (till exam)\n\n💳 UPI: 9907843768@ybl\n📸 After payment, tap ✅ Done below.",
                   reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "paid_done")
def paid_done(call):
    bot.send_message(call.message.chat.id,
                     "✅ Payment step completed!\n\n📌 Please join the approval channel to verify your payment:\n👉 @NEETPremiumVerify")

@bot.message_handler(commands=['mcq'])
def mcq(message):
    with open("mcqs.json", "r") as f:
        mcqs = json.load(f)
    bio = mcqs.get("biology", [])
    text = "🧠 Today's Biology MCQs:\n\n"
    for i, q in enumerate(bio[:5], 1):
        text += f"{i}. {q}\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['notes'])
def notes(message):
    try:
        with open("notes/sample_note.txt", "r") as f:
            note = f.read()
        bot.send_message(message.chat.id, f"📘 Sample Note:\n\n{note}")
    except:
        bot.send_message(message.chat.id, "⚠️ Notes not available right now.")

bot.polling()
