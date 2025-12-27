# 🤖 Telegram PA Bot (IST)

A persistent, timezone-aware (IST) Personal Assistant bot for Telegram. It handles one-time reminders, recurring tasks, and team reminders using natural language processing.

## ✨ Features

* **Natural Language:** Just speak naturally (e.g., *"in 10 minutes"*, *"tomorrow at 5pm"*).
* **Persistent Memory:** Reminders are saved to a local database (`reminders.db`). They survive PC restarts and power failures.
* **Missed Reminder Reports:** If the bot is offline when a reminder is due, it sends you a report the moment it comes back online.
* **Team Mode:** Set reminders for other users by tagging their username (e.g., `Remind @john...`).
* **Recurring Tasks:** Supports Daily and Weekly repetition.
* **Hardcoded IST:** All times are strictly calculated in Indian Standard Time.

---

## 🛠️ Installation

1. **Prerequisites:**
* Python 3.9+
* A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))


2. **Install Dependencies:**
```bash
pip install python-telegram-bot dateparser pytz

```


3. **Configuration:**
* Open `pa_bot.py`.
* Replace `YOUR_TELEGRAM_BOT_TOKEN_HERE` with your actual token.


4. **Run:**
```bash
python pa_bot.py

```



---

## 📝 Command Syntax Guide

The bot uses a **"Tail Parsing"** strategy. This means you should write the **Message first** and the **Time at the end**.

### 1. Simple Reminders

**Format:** `Remind me to [Task] [Time]`

| Type | Example Command |
| --- | --- |
| **Relative Time** | `Remind me to check the server in 10 minutes` |
| **Specific Time** | `Remind me to call the client at 4pm` |
| **Tomorrow** | `Remind me to submit the report tomorrow at 11am` |
| **Specific Date** | `Remind me to pay bills on 25th Dec at 10am` |

### 2. Recurring Reminders

Add **"every day"**, **"daily"**, **"every week"**, or **"weekly"** to the message.

| Frequency | Example Command |
| --- | --- |
| **Daily** | `Remind me to drink water every day at 9am` |
| **Daily (Alt)** | `Remind me to send status report daily at 6pm` |
| **Weekly** | `Remind me to clean the desk every week at 5pm` |

### 3. Reminding Others (Team Mode)

**Format:** `Remind @username to [Task] [Time]`

> **⚠️ Important:** The target user (e.g., `@alice`) must have started a chat with the bot (`/start`) at least once before, or the bot won't be able to message them.

| Scenario | Example Command |
| --- | --- |
| **Delegate Task** | `Remind @alice to upload the logs in 20 mins` |
| **Team Update** | `Remind @bob to join the zoom call at 3pm` |

---

## ⚙️ Management Commands

These are the slash commands used to manage the bot.

| Command | Description |
| --- | --- |
| `/start` | Registers you in the system. (Required for everyone). |
| `/list` | Shows all **pending** reminders created by you or set for you. Shows the **ID** needed to delete them. |
| `/delete [ID]` | Deletes a reminder. Example: `/delete 5` |

---

## ❓ Troubleshooting / FAQ

**Q: I tried to remind @friend, but the bot said "I don't know them".**
**A:** Telegram bots cannot message users who haven't messaged them first. Ask your friend to search for your bot and click **Start**.

**Q: The bot set the reminder for the wrong date (e.g., next year).**
**A:** This happens if the time phrased is ambiguous. Try to be specific.

* *Bad:* `Remind me check server 3` (3 what? pm? am? date?)
* *Good:* `Remind me to check server at 3pm`

**Q: Where are the reminders stored?**
**A:** In a file named `reminders.db` created in the same folder as the script. Back up this file to save your data.

**Q: I restarted my computer. Will the reminders still work?**
**A:** Yes. Once you run the script again, the bot will load the database and immediately report any reminders that were missed while the computer was off.
