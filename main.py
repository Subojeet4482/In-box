import os
import asyncio
import threading
from flask import Flask
from dotenv import load_dotenv
load_dotenv()

import aiohttp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN env me set nahi hai")

if not ADMIN_ID_RAW:
    raise ValueError("ADMIN_ID env me set nahi hai")

ADMIN_ID = int(ADMIN_ID_RAW)

UPTIME_URLS = [
    os.environ.get("SELF_URL", "")  # optional self-ping
]

# ================= STORAGE =================
USER_MAP = {}      # forwarded_msg_id -> user_id
USERS = {}         # user_id -> info
BLOCKED = set()

# ================= WEB SERVER (UPTIME) =================
web = Flask(__name__)

@web.route("/")
def home():
    return "🤖 Bot Alive", 200

def run_web():
    web.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n"
        "Aap jo bhi bhejoge admin tak jayega.\n"
        "Reply ka wait karein 🙂"
    )

# ================= USER → ADMIN =================
async def user_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message

    if user.id == ADMIN_ID:
        return
    if user.id in BLOCKED:
        return

    username = user.username or "NoUsername"

    USERS[user.id] = {
        "name": user.first_name,
        "username": username
    }

    info = (
        "👤 New Message\n"
        f"• Name: {user.first_name}\n"
        f"• Username: @{username}\n"
        f"• ID: {user.id}"
    )

    await context.bot.send_message(ADMIN_ID, info)

    fwd = await msg.forward(ADMIN_ID)
    USER_MAP[fwd.message_id] = user.id

    await msg.reply_text("✅ Sent to admin")

# ================= ADMIN → USER =================
async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.reply_to_message:
        return

    mid = update.message.reply_to_message.message_id
    user_id = USER_MAP.get(mid)

    if not user_id:
        await update.message.reply_text("❌ User not found")
        return
    if user_id in BLOCKED:
        await update.message.reply_text("🚫 User blocked")
        return

    await update.message.copy(chat_id=user_id)
    await update.message.reply_text("✅ Delivered")

# ================= COMMANDS =================
async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /block user_id")
        return

    uid = int(context.args[0])
    BLOCKED.add(uid)
    await update.message.reply_text(f"🚫 Blocked {uid}")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /unblock user_id")
        return

    uid = int(context.args[0])
    BLOCKED.discard(uid)
    await update.message.reply_text(f"✅ Unblocked {uid}")

async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not USERS:
        await update.message.reply_text("No users yet")
        return

    text = "👥 Users:\n\n"
    for uid, info in USERS.items():
        text += f"{info['name']} (@{info['username']}) → {uid}\n"

    await update.message.reply_text(text)

# ================= UPTIME LOOP =================
async def uptime_loop():
    if not UPTIME_URLS:
        return

    async with aiohttp.ClientSession() as session:
        while True:
            for url in UPTIME_URLS:
                if not url:
                    continue
                try:
                    async with session.get(url, timeout=10):
                        pass
                except:
                    pass
            await asyncio.sleep(300)

# ================= MAIN =================
def main():
    threading.Thread(target=run_web, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("block", block_user))
    app.add_handler(CommandHandler("unblock", unblock_user))
    app.add_handler(CommandHandler("users", users_list))

    app.add_handler(MessageHandler(filters.REPLY & filters.ALL, admin_reply))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, user_to_admin))

    async def on_start(app):
        asyncio.create_task(uptime_loop())

    app.post_init = on_start

    print("🤖 Production Inbox Bot Running")
    app.run_polling()

if __name__ == "__main__":
    main()
