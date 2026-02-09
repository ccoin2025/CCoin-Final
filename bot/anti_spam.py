import re
import time
from collections import defaultdict
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

ALLOWED_BOT = "CTG_COIN_BOT"
GROUP_ID = -1003758615666

MESSAGE_INTERVAL = 10
user_last_message = defaultdict(float)

LINK_REGEX = re.compile(r"(http[s]?://|t\.me/|www\.)", re.IGNORECASE)
BOT_MENTION_REGEX = re.compile(r"@\w+bot", re.IGNORECASE)

async def anti_spam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    if message.chat_id != GROUP_ID:
        return

    user_id = message.from_user.id
    text = message.text
    now = time.time()

    if now - user_last_message[user_id] < MESSAGE_INTERVAL:
        await message.delete()
        await context.bot.restrict_chat_member(
            chat_id=message.chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=now + 60
        )
        return

    user_last_message[user_id] = now

    if LINK_REGEX.search(text):
        await message.delete()
        return

    for mention in BOT_MENTION_REGEX.findall(text):
        if ALLOWED_BOT_USERNAME.lower() not in mention.lower():
            await message.delete()
            return
