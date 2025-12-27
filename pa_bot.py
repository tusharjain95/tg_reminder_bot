import logging
import sqlite3
import re
import datetime
import pytz
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import dateparser

# --- CONFIGURATION ---
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"  # <--- PASTE YOUR TOKEN HERE
IST = pytz.timezone('Asia/Kolkata')
DB_NAME = "reminders.db"

# --- LOGGING SETUP ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- DATABASE MANAGEMENT ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  creator_id INTEGER,
                  target_chat_id INTEGER,
                  target_username TEXT,
                  message TEXT,
                  remind_time TEXT, 
                  is_recurring BOOLEAN,
                  recurrence_type TEXT,
                  status TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, chat_id INTEGER)''')
    conn.commit()
    conn.close()

def save_user(username, chat_id):
    if not username: return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    clean_username = username.replace('@', '').lower()
    c.execute("INSERT OR REPLACE INTO users (username, chat_id) VALUES (?, ?)", (clean_username, chat_id))
    conn.commit()
    conn.close()

def get_chat_id_by_username(username):
    if not username: return None
    clean_username = username.replace('@', '').lower()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT chat_id FROM users WHERE username = ?", (clean_username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# --- LOGIC HELPERS ---
def get_ist_now():
    return datetime.datetime.now(IST)

def parse_reminder_text(text):
    """
    Robust 'Tail Parsing' Strategy.
    1. Removes 'Remind @user to' prefix.
    2. Scans from the END of the sentence to find the longest valid date string.
    """
    # 1. Extract Target User & Clean Command Prefix
    target_username = None
    clean_text = text
    
    # Regex to find "Remind @user/me (to)" at the start
    match = re.match(r"^(remind|remind)\s+(@\w+|me)\s+(to\s+)?", text, re.IGNORECASE)
    if match:
        user_part = match.group(2)
        if user_part.lower() != 'me':
            target_username = user_part
        # Remove the prefix from text
        clean_text = text[match.end():]

    # 2. Detect Recurrence keywords
    recurrence = None
    if "every day" in clean_text.lower() or "daily" in clean_text.lower():
        recurrence = "daily"
    elif "every week" in clean_text.lower() or "weekly" in clean_text.lower():
        recurrence = "weekly"

    # 3. Tail Parsing for Date
    words = clean_text.split()
    best_date = None
    split_index = len(words) # Default: if no date found, whole text is message
    
    # Settings: Future preference ensures "4pm" means "Next 4pm" (today or tomorrow)
    settings = {
        'TIMEZONE': 'Asia/Kolkata', 
        'TO_TIMEZONE': 'Asia/Kolkata',
        'PREFER_DATES_FROM': 'future',
        'RETURN_AS_TIMEZONE_AWARE': True
    }

    # Iterate backwards: check "tomorrow", then "3pm tomorrow", then "at 3pm tomorrow"...
    for i in range(len(words) - 1, -1, -1):
        candidate_phrase = " ".join(words[i:])
        
        # Skip purely numeric candidates to avoid parsing "2" as a date in "Buy 2 apples"
        if candidate_phrase.isdigit():
            continue

        dt = dateparser.parse(candidate_phrase, settings=settings)
        
        if dt:
            # We found a valid date.
            best_date = dt
            split_index = i
            # We continue the loop? No, usually the longest valid suffix is the best.
            # But "Server at 4pm" -> "4pm" is valid, "at 4pm" is valid, "Server at 4pm" is invalid.
            # So as soon as we hit an invalid one after finding a valid one, we know the boundary.
        else:
            # If we previously found a date, but adding this word made it invalid, 
            # then the previous match was the correct time phrase.
            if best_date:
                break
    
    # 4. Final Assembly
    if best_date:
        message_body = " ".join(words[:split_index])
    else:
        message_body = clean_text # No date found

    # Remove recurrence keywords from message if they exist
    if recurrence:
        message_body = re.sub(r"(every day|daily|every week|weekly)", "", message_body, flags=re.IGNORECASE).strip()

    # Safety: Ensure TZ is correct
    if best_date and best_date.tzinfo is None:
        best_date = IST.localize(best_date)

    return target_username, message_body.strip(), best_date, recurrence

# --- BOT COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.username, update.effective_chat.id)
    await update.message.reply_text(
        f"Hi {user.first_name}! I am your PA Bot (IST).\n\n"
        "**Try these commands:**\n"
        "1. `Remind me to check server at 4pm`\n"
        "2. `Remind me to call mom tomorrow at 10am`\n"
        "3. `Remind @john to submit report in 20 mins`\n"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    save_user(user.username, update.effective_chat.id)

    if not text.lower().startswith("remind"):
        return

    target_user, msg, time_obj, recurrence = parse_reminder_text(text)

    if not time_obj:
        await update.message.reply_text("❓ I found the message but **no time**. Please add a time at the end.\nExample: `...at 5pm` or `...in 10 mins`")
        return
    
    # Check if time is in past (Allow 1 minute buffer for processing time)
    now = get_ist_now()
    if time_obj < (now - datetime.timedelta(minutes=1)):
        await update.message.reply_text(
            f"⚠️ That time ({time_obj.strftime('%d-%b %H:%M')}) is in the past.\n"
            f"Since I use 'Future' mode, this usually means I couldn't interpret '{text.split()[-1]}' correctly.\n"
            "Try being more specific: 'Tomorrow at 3pm' instead of just '3pm'."
        )
        return

    # Determine Target
    target_chat_id = update.effective_chat.id
    target_handle = "You"
    
    if target_user:
        looked_up_id = get_chat_id_by_username(target_user)
        if looked_up_id:
            target_chat_id = looked_up_id
            target_handle = target_user
        else:
            await update.message.reply_text(f"⚠️ I don't know {target_user}. Setting reminder for YOU instead.")

    # Save to DB
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO reminders (creator_id, target_chat_id, target_username, message, remind_time, is_recurring, recurrence_type, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                 (update.effective_chat.id, target_chat_id, target_user, msg, time_obj.isoformat(), 1 if recurrence else 0, recurrence, 'pending'))
    conn.commit()
    conn.close()

    recur_msg = f" (Repeating: {recurrence})" if recurrence else ""
    await update.message.reply_text(f"✅ Saved!\nMsg: **{msg}**\nTime: **{time_obj.strftime('%d-%b %I:%M %p')}**{recur_msg}")

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, message, remind_time, target_username FROM reminders WHERE (creator_id=? OR target_chat_id=?) AND status='pending'", 
              (update.effective_chat.id, update.effective_chat.id))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No pending reminders.")
        return

    response = "📅 **Pending Reminders:**\n\n"
    for row in rows:
        rid, msg, time_str, target = row
        try:
            dt = datetime.datetime.fromisoformat(time_str)
            if dt.tzinfo is None: dt = IST.localize(dt)
            fmt_time = dt.strftime('%d-%b %I:%M %p')
        except:
            fmt_time = time_str
            
        tgt_str = f"👉 {target}" if target else ""
        response += f"🆔 `{rid}`: {fmt_time} {tgt_str}\n📝 {msg}\n\n"
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rid = int(context.args[0])
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM reminders WHERE id=? AND creator_id=?", (rid, update.effective_chat.id))
        if c.rowcount > 0:
            await update.message.reply_text(f"Deleted reminder ID {rid}.")
        else:
            await update.message.reply_text("ID not found.")
        conn.commit()
        conn.close()
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /delete [ID]")

# --- BACKGROUND TASKS ---

async def check_reminders_loop(context: ContextTypes.DEFAULT_TYPE):
    now = get_ist_now()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check for times <= NOW
    c.execute("SELECT id, creator_id, target_chat_id, message, recurrence_type FROM reminders WHERE status='pending' AND remind_time <= ?", (now.isoformat(),))
    due_reminders = c.fetchall()

    for row in due_reminders:
        rid, creator_id, target_id, msg, recurrence = row
        try:
            await context.bot.send_message(chat_id=target_id, text=f"🔔 **REMINDER** 🔔\n\n{msg}")
            
            if creator_id != target_id:
                await context.bot.send_message(chat_id=creator_id, text=f"✅ Delivered: {msg}")

            if recurrence:
                old_time_str = c.execute("SELECT remind_time FROM reminders WHERE id=?", (rid,)).fetchone()[0]
                old_time = datetime.datetime.fromisoformat(old_time_str)
                if old_time.tzinfo is None: old_time = IST.localize(old_time)

                if recurrence == 'daily':
                    next_time = old_time + datetime.timedelta(days=1)
                elif recurrence == 'weekly':
                    next_time = old_time + datetime.timedelta(weeks=1)
                else:
                    next_time = old_time + datetime.timedelta(days=1)

                c.execute("UPDATE reminders SET remind_time = ? WHERE id = ?", (next_time.isoformat(), rid))
            else:
                c.execute("UPDATE reminders SET status = 'sent' WHERE id = ?", (rid,))
        except Exception as e:
            logging.error(f"Failed to send reminder {rid}: {e}")
            
    conn.commit()
    conn.close()

async def report_missed_reminders(app):
    now = get_ist_now()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    cutoff = now - datetime.timedelta(minutes=2)
    
    c.execute("SELECT id, creator_id, message, remind_time FROM reminders WHERE status='pending' AND remind_time < ?", (cutoff.isoformat(),))
    missed = c.fetchall()
    
    for row in missed:
        rid, creator_id, msg, time_str = row
        try:
            await app.bot.send_message(chat_id=creator_id, text=f"⚠️ **MISSED WHILE OFFLINE**\nTime: {time_str}\nMsg: {msg}")
            c.execute("UPDATE reminders SET status = 'missed_offline' WHERE id = ?", (rid,))
        except:
            pass
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_reminders))
    app.add_handler(CommandHandler("delete", delete_reminder))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    app.job_queue.run_repeating(check_reminders_loop, interval=60, first=10)
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(report_missed_reminders(app))

    print("Bot is running...")
    app.run_polling()
