import logging
import sqlite3
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8623226804:AAGjHtYFc3xr0PKIA1swUNMGo6j4hbfL1do"
DB_NAME = "anime_bot.db"
MESSAGE_THRESHOLD = 100
ADMIN_ID = 6267038708

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

RARITY_REWARD = {"Common": 50, "Rare": 150, "Epic": 400, "Legendary": 1000}
RARITY_EMOJI = {"Common": "⚪", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}
RARITY_WEIGHTS = [50, 30, 15, 5]
RARITY_LIST = ["Common", "Rare", "Epic", "Legendary"]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        coins INTEGER DEFAULT 100,
        total_catches INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS collection (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        char_code INTEGER,
        caught_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS active_char (
        chat_id INTEGER PRIMARY KEY,
        char_code INTEGER,
        active INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_stats (
        chat_id INTEGER PRIMARY KEY,
        message_count INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS characters (
        code INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        rarity TEXT,
        video_id TEXT
    )''')
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username or user.first_name))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"سلام {user.first_name}! 🎮\n\n"
        "من ربات شکار انیمه هستم! 🎯\n\n"
        "📋 **دستورات:**\n"
        "/menu - منوی اصلی\n"
        "/me - پروفایل من\n"
        "/collection - کلکسیون من\n"
        "/top - جدول امتیازات\n"
        "/s <کد> - نمایش یه کاراکتر\n"
        "/info <کد> - اطلاعات کاراکتر\n\n"
        "💡 هر ۱۰۰ پیام توی گروه، یه کاراکتر ظاهر میشه!",
        parse_mode="Markdown"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎯 **منوی AnimeGrab**\n\n"
        "👤 **کاربری:**\n"
        "/me - پروفایل و سکه\n"
        "/collection - کلکسیون\n"
        "/top - ۱۰ نفر برتر\n\n"
        "🔍 **جستجو:**\n"
        "/s <کد> - نمایش کاراکتر\n"
        "/info <کد> - اطلاعات کاراکتر\n\n"
        "⚙️ **ادمین:**\n"
        "/spawn - فرستادن کاراکتر\n"
        "/addchar - راهنمای اضافه کردن\n"
        "/listchars - لیست کاراکترها\n"
        "/delchar <کد> - حذف",
        parse_mode="Markdown"
    )

async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username or user.first_name))
    conn.commit()
    c.execute("SELECT coins, total_catches FROM users WHERE user_id = ?", (user.id,))
    row = c.fetchone()
    c.execute("SELECT COUNT(DISTINCT char_code) FROM collection WHERE user_id = ?", (user.id,))
    unique_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM characters")
    total_chars = c.fetchone()[0]
    c.execute("SELECT COUNT(*) + 1 FROM users WHERE total_catches > ?", (row[1],))
    rank = c.fetchone()[0]
    conn.close()
    
    coins, catches = row
    await update.message.reply_text(
        f"👤 **پروفایل {user.first_name}**\n\n"
        f"💰 سکه: **{coins}**\n"
        f"🎯 کل شکار: **{catches}**\n"
        f"📚 کاراکترهای یکتا: **{unique_count}/{total_chars}**\n"
        f"🏆 رتبه: **#{rank}**",
        parse_mode="Markdown"
    )

async def collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""SELECT ch.code, ch.name, ch.rarity, COUNT(cl.id) 
                 FROM collection cl 
                 JOIN characters ch ON cl.char_code = ch.code 
                 WHERE cl.user_id = ? 
                 GROUP BY ch.code 
                 ORDER BY ch.rarity, ch.name""", (user.id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("هنوز هیچ کاراکتری شکار نکردی! 😢")
        return
    text = f"📚 **کلکسیون {user.first_name}**\n\n"
    for code, name, rarity, count in rows:
        emoji = RARITY_EMOJI.get(rarity, "⚪")
        text += f"{emoji} `#{code}` {name} ×{count}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT username, total_catches, coins FROM users ORDER BY total_catches DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    text = "🏆 **۱۰ شکارچی برتر**\n\n"
    for i, (name, catches, coins) in enumerate(rows, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += f"{medal} {name} - {catches} شکار (💰{coins})\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def show_char(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("مثال: `/s 9`", parse_mode="Markdown")
        return
    try:
        code = int(context.args[0])
    except:
        await update.message.reply_text("❌ کد باید عدد باشه!")
        return
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT code, name, rarity, video_id FROM characters WHERE code = ?", (code,))
    char = c.fetchone()
    if not char:
        conn.close()
        await update.message.reply_text(f"❌ کاراکتری با کد `{code}` پیدا نشد!", parse_mode="Markdown")
        return
    
    c.execute("SELECT COUNT(DISTINCT user_id) FROM collection WHERE char_code = ?", (code,))
    owners = c.fetchone()[0]
    conn.close()
    
    ch_code, name, rarity, video_id = char
    emoji = RARITY_EMOJI.get(rarity, "⚪")
    caption = (
        f"{emoji} **{name}**\n\n"
        f"🔢 کد: `#{ch_code}`\n"
        f"📊 سطح: {rarity}\n"
        f"👥 صاحبان: **{owners}** نفر"
    )
    try:
        await update.message.reply_video(video=video_id, caption=caption, parse_mode="Markdown")
    except:
        await update.message.reply_text(caption, parse_mode="Markdown")

async def info_char(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("مثال: `/info 9`", parse_mode="Markdown")
        return
    try:
        code = int(context.args[0])
    except:
        await update.message.reply_text("❌ کد باید عدد باشه!")
        return
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT code, name, rarity FROM characters WHERE code = ?", (code,))
    char = c.fetchone()
    if not char:
        conn.close()
        await update.message.reply_text(f"❌ کاراکتری با کد `{code}` پیدا نشد!", parse_mode="Markdown")
        return
    
    c.execute("SELECT COUNT(DISTINCT user_id) FROM collection WHERE char_code = ?", (code,))
    owners = c.fetchone()[0]
    
    c.execute("""SELECT u.username FROM collection cl 
                 JOIN users u ON cl.user_id = u.user_id 
                 WHERE cl.char_code = ? 
                 GROUP BY u.user_id LIMIT 5""", (code,))
    top_owners = [r[0] for r in c.fetchall()]
    conn.close()
    
    ch_code, name, rarity = char
    emoji = RARITY_EMOJI.get(rarity, "⚪")
    reward = RARITY_REWARD.get(rarity, 50)
    text = (
        f"📊 **اطلاعات کاراکتر**\n\n"
        f"{emoji} نام: **{name}**\n"
        f"🔢 کد: `#{ch_code}`\n"
        f"📈 سطح: {rarity}\n"
        f"💰 پاداش شکار: {reward} سکه\n"
        f"👥 تعداد صاحبان: **{owners}**\n\n"
    )
    if top_owners:
        text += "🏅 **اولین شکارچی‌ها:**\n"
        for i, owner in enumerate(top_owners, 1):
            text += f"{i}. {owner}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def addchar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ فقط ادمین!")
        return
    await update.message.reply_text(
        "📤 **راهنمای اضافه کردن کاراکتر:**\n\n"
        "فقط یه ویدیو بفرست با کپشن اسم کاراکتر:\n"
        "`Naruto`\n\n"
        "سطح به صورت تصادفی انتخاب میشه! 🎲\n\n"
        "شانس سطوح:\n"
        "⚪ Common: ۵۰٪\n"
        "🔵 Rare: ۳۰٪\n"
        "🟣 Epic: ۱۵٪\n"
        "🟡 Legendary: ۵٪",
        parse_mode="Markdown"
    )

async def listchars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ فقط ادمین!")
        return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT code, name, rarity FROM characters ORDER BY code")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("هیچ کاراکتری اضافه نشده!")
        return
    text = f"📋 **لیست کاراکترها ({len(rows)} تا):**\n\n"
    for code, name, rarity in rows:
        emoji = RARITY_EMOJI.get(rarity, "⚪")
        text += f"`#{code}` {emoji} {name}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def delchar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ فقط ادمین!")
        return
    if not context.args:
        await update.message.reply_text("مثال: `/delchar 9`", parse_mode="Markdown")
        return
    try:
        code = int(context.args[0])
    except:
        await update.message.reply_text("❌ کد باید عدد باشه!")
        return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM characters WHERE code = ?", (code,))
    conn.commit()
    if c.rowcount > 0:
        await update.message.reply_text(f"✅ کاراکتر `#{code}` حذف شد!", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ کاراکتری با کد `{code}` پیدا نشد!", parse_mode="Markdown")
    conn.close()

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    
    message = update.message
    video = message.video or message.animation
    caption = message.caption
    
    if not video:
        return
    
    if not caption:
        await message.reply_text("❌ کپشن رو خالی گذاشتی! اسم کاراکتر رو بنویس.")
        return
    
    name = caption.strip()
    if "|" in name:
        name = name.split("|")[0].strip()
    
    rarity = random.choices(RARITY_LIST, weights=RARITY_WEIGHTS, k=1)[0]
    file_id = video.file_id
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT OR REPLACE INTO characters (name, rarity, video_id) VALUES (?, ?, ?)",
                  (name, rarity, file_id))
        conn.commit()
        c.execute("SELECT code FROM characters WHERE name = ?", (name,))
        code = c.fetchone()[0]
        emoji = RARITY_EMOJI.get(rarity, "⚪")
        await message.reply_text(
            f"✅ کاراکتر اضافه شد!\n\n"
            f"🔢 کد: `#{code}`\n"
            f"📛 نام: **{name}**\n"
            f"{emoji} سطح: {rarity}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.reply_text(f"❌ خطا: {e}")
    finally:
        conn.close()

async def spawn_char(context, chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT active FROM active_char WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    if row and row[0] == 1:
        conn.close()
        return
    
    c.execute("SELECT code, name, rarity, video_id FROM characters ORDER BY RANDOM() LIMIT 1")
    char = c.fetchone()
    
    if not char:
        conn.close()
        await context.bot.send_message(chat_id=chat_id, text="⚠️ هیچ کاراکتری توی دیتابیس نیست! ادمین باید کاراکتر اضافه کنه.")
        return
    
    ch_code, name, rarity, video_id = char
    c.execute("REPLACE INTO active_char (chat_id, char_code, active) VALUES (?, ?, 1)",
              (chat_id, ch_code))
    conn.commit()
    conn.close()
    
    emoji = RARITY_EMOJI.get(rarity, "⚪")
    caption = (
        f"🎬 یه کاراکتر ظاهر شد!\n\n"
        f"{emoji} سطح: {rarity}\n\n"
        "⏰ ۶۰ ثانیه وقت داری اسمش رو حدس بزنی!\n"
        "✍️ فقط اسم کاراکتر رو توی چت بنویس!"
    )
    try:
        await context.bot.send_video(chat_id=chat_id, video=video_id, caption=caption)
    except Exception as e:
        print(f"خطا: {e}")
        await context.bot.send_message(chat_id=chat_id, text=caption)

async def spawn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await spawn_char(context, update.effective_chat.id)

async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()
    
    if text.startswith("/"):
        return
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("INSERT OR IGNORE INTO chat_stats (chat_id, message_count) VALUES (?, 0)", (chat_id,))
    c.execute("UPDATE chat_stats SET message_count = message_count + 1 WHERE chat_id = ?", (chat_id,))
    c.execute("SELECT message_count FROM chat_stats WHERE chat_id = ?", (chat_id,))
    count = c.fetchone()[0]
    
    if count >= MESSAGE_THRESHOLD:
        c.execute("UPDATE chat_stats SET message_count = 0 WHERE chat_id = ?", (chat_id,))
        conn.commit()
        conn.close()
        await spawn_char(context, chat_id)
        return
    
    c.execute("""SELECT ch.code, ch.name, ch.rarity, ac.active 
                 FROM active_char ac 
                 JOIN characters ch ON ac.char_code = ch.code 
                 WHERE ac.chat_id = ?""", (chat_id,))
    row = c.fetchone()
    
    if not row or row[3] != 1:
        conn.close()
        return
    
    ch_code, char_name, rarity, _ = row
    
    if text.lower() == char_name.lower():
        c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                  (user.id, user.username or user.first_name))
        reward = RARITY_REWARD.get(rarity, 50)
        c.execute("UPDATE users SET coins = coins + ?, total_catches = total_catches + 1 WHERE user_id = ?",
                  (reward, user.id))
        c.execute("INSERT INTO collection (user_id, char_code) VALUES (?, ?)",
                  (user.id, ch_code))
        c.execute("UPDATE active_char SET active = 0 WHERE chat_id = ?", (chat_id,))
        conn.commit()
        conn.close()
        
        emoji = RARITY_EMOJI.get(rarity, "⚪")
        await update.message.reply_text(
            f"🎉 **شکار موفق!**\n\n"
            f"{emoji} {user.first_name} کاراکتر **{char_name}** (`#{ch_code}`) رو شکار کرد!\n"
            f"💰 +{reward} سکه",
            parse_mode="Markdown"
        )
    else:
        conn.close()

def main():
    init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("me", me))
    application.add_handler(CommandHandler("collection", collection))
    application.add_handler(CommandHandler("top", top))
    application.add_handler(CommandHandler("s", show_char))
    application.add_handler(CommandHandler("info", info_char))
    application.add_handler(CommandHandler("spawn", spawn))
    application.add_handler(CommandHandler("addchar", addchar))
    application.add_handler(CommandHandler("listchars", listchars))
    application.add_handler(CommandHandler("delchar", delchar))
    application.add_handler(MessageHandler(filters.VIDEO | filters.ANIMATION, handle_video))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guess))
    print("🤖 AnimeGrab bot started!")
    application.run_polling()

if __name__ == "__main__":
    main()
