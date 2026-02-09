import re
import time
import asyncio
from collections import defaultdict
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

# ===============================
# CONFIG
# ===============================
GROUP_ID = -1003758615666          # YOUR SUPERGROUP ID
ALLOWED_BOT = "CTG_COIN_BOT"       # ONLY THIS BOT CAN BE MENTIONED

MESSAGE_INTERVAL = 10              # seconds between messages
WARNING_LIMIT = 3                  # warnings before temp ban
TEMP_BAN_DURATION = 12 * 3600      # 12 hours (in seconds)
WARNING_DELETE_DELAY = 10          # delete warning messages after 10 seconds
# ===============================

# user state
user_last_message = defaultdict(float)
user_warnings = defaultdict(int)
user_temp_banned = defaultdict(bool)

# regex rules
LINK_REGEX = re.compile(r"(http[s]?://|t\.me/|www\.)", re.IGNORECASE)
BOT_MENTION_REGEX = re.compile(r"@\w+bot", re.IGNORECASE)


async def delete_later(message, delay=WARNING_DELETE_DELAY):
    """Delete a message after delay without blocking"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass


async def anti_spam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    if message.chat_id != GROUP_ID:
        return

    user_id = message.from_user.id
    username = message.from_user.first_name or message.from_user.username or "User"
    text = message.text
    now = time.time()

    # --------------------------------
    # SPAM: MESSAGE INTERVAL
    # --------------------------------
    if now - user_last_message[user_id] < MESSAGE_INTERVAL:
        await handle_violation(context, message, user_id, username, "sending messages too fast")
        return

    user_last_message[user_id] = now

    # --------------------------------
    # LINKS
    # --------------------------------
    if LINK_REGEX.search(text):
        await handle_violation(context, message, user_id, username, "posting links")
        return

    # --------------------------------
    # BOT MENTIONS
    # --------------------------------
    for mention in BOT_MENTION_REGEX.findall(text):
        if ALLOWED_BOT.lower() not in mention.lower():
            await handle_violation(context, message, user_id, username, "mentioning other bots")
            return


async def handle_violation(context, message, user_id, username, reason):
    # delete offending message
    await message.delete()

    # --------------------------------
    # PERMANENT BAN (AFTER TEMP BAN)
    # --------------------------------
    if user_temp_banned[user_id]:
        await context.bot.restrict_chat_member(
            chat_id=GROUP_ID,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False)
        )

        ban_msg = await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"🚫 {username} has been permanently banned for repeated violations ({reason})."
        )

        asyncio.create_task(delete_later(ban_msg))
        return

    # --------------------------------
    # WARNINGS
    # --------------------------------
    user_warnings[user_id] += 1

    if user_warnings[user_id] < WARNING_LIMIT:
        warn_msg = await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"⚠️ {username}, please stop {reason}! Warning {user_warnings[user_id]}/{WARNING_LIMIT}."
        )

        asyncio.create_task(delete_later(warn_msg))

    else:
        # --------------------------------
        # TEMP BAN (12 HOURS)
        # --------------------------------
        until = time.time() + TEMP_BAN_DURATION

        await context.bot.restrict_chat_member(
            chat_id=GROUP_ID,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until
        )

        ban_msg = await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"⏰ {username} has been temporarily banned for 12 hours due to repeated violations ({reason})."
        )

        user_temp_banned[user_id] = True
        user_warnings[user_id] = 0

        asyncio.create_task(delete_later(ban_msg))
