import re
import time
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes

ALLOWED_BOT = "@YourAirdropBot"
MESSAGE_LIMIT_SECONDS = 10

user_last_message = defaultdict(float)

LINK_REGEX = re.compile(r"(http[s]?://|t\.me/|www\.)", re.IGNORECASE)
BOT_MENTION_REGEX = re.compile(r"@\w+bot", re.IGNORECASE)

async def anti_spam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id
    text = message.text or ""

    now = time.time()

    # flood control
    if now - user_last_message[user_id] < MESSAGE_LIMIT_SECONDS:
        await message.delete()
        await context.bot.restrict_chat_member(
            chat_id=message.chat_id,
            user_id=user_id,
            permissions=None,
            until_date=now + 60
        )
        return

    user_last_message[user_id] = now

    # block links
    if LINK_REGEX.search(text):
        await message.delete()
        return

    # block other bots mention
    bot_mentions = BOT_MENTION_REGEX.findall(text)
    for bot in bot_mentions:
        if bot.lower() != ALLOWED_BOT.lower():
            await message.delete()
            return
