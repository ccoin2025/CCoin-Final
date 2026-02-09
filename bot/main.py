from telegram.ext import Application, MessageHandler, filters
from anti_spam import anti_spam_handler

app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam_handler)
)

app.initialize()
