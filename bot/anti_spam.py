import re
import time
from collections import defaultdict
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

# -------------------------------
# CONFIGURATION
# -------------------------------
ALLOWED_BOT = "CTG_COIN_BOT"        # only this bot can be mentioned
GROUP_ID = -1003758615666            # your supergroup chat ID
MESSAGE_INTERVAL = 10                # seconds between messages
WARNING_LIMIT = 3                     # warnings before temporary ban
TEMP_BAN_DURATION = 12 * 3600        # 12 hours in seconds
# -------------------------------

# track last message time per user
user_last_message = defaultdict(float)

# track warnings per user
user_warnings = defaultdict(int)

# track if user was already temp-banned
user_temp_banned = defaultdict(bool)

# regex to detect links and bot mentions
LINK_REGEX = re.compile(r"(http[s]?://|t\.me/|www\.)", re.IGNORECASE)
BOT_MENTION_REGEX = re.compile(r"@\w+bot", re.IGNORECASE)


async def anti_spam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    if message.chat_id != GROUP_ID:
        return

    user_id = message.from_user.id
    username = message.from_user.first_name or message.from_user.username
    text = message.text
    now = time.time()

    # -------------------------------
    # CHECK MESSAGE INTERVAL (SPAM)
    # -------------------------------
    if now - user_last_message[user_id] < MESSAGE_INTERVAL:
        await handle_violation(context, message, user_id, username, reason="sending messages too fast")
        return

    user_last_message[user_id] = now

    # -------------------------------
    # CHECK LINKS
    # -------------------------------
    if LINK_REGEX.search(text):
        await handle_violation(context, message, user_id, username, reason="posting links")
        return

    # -------------------------------
    # CHECK OTHER BOT MENTIONS
    # -------------------------------
    for mention in BOT_MENTION_REGEX.findall(text):
        if ALLOWED_BOT.lower() not in mention.lower():
            await handle_violation(context, message, user_id, username, reason="mentioning other bots")
            return


async def handle_violation(context, message, user_id, username, reason):
    """Handle warnings, temporary and permanent bans"""
    # delete the offending message
    await message.delete()

    # if user was already temp banned, now permanent ban
    if user_temp_banned[user_id]:
        await context.bot.restrict_chat_member(
            chat_id=GROUP_ID,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False)
        )
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"🚫 {username} has been permanently banned for repeated violations ({reason})."
        )
        return

    # increase warning count
    user_warnings[user_id] += 1

    # check warning limit
    if user_warnings[user_id] < WARNING_LIMIT:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"⚠️ {username}, please stop {reason}! Warning {user_warnings[user_id]}/{WARNING_LIMIT}."
        )
    else:
        # temporary ban 12 hours
        now = time.time()
        await context.bot.restrict_chat_member(
            chat_id=GROUP_ID,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=now + TEMP_BAN_DURATION
        )
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"⏰ {username} has been temporarily banned for 12 hours due to repeated violations ({reason})."
        )
        # mark as temp-banned
        user_temp_banned[user_id] = True
        # reset warnings
        user_warnings[user_id] = 0
