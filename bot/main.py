from telegram.ext import ApplicationBuilder, MessageHandler, filters
from anti_spam import anti_spam_handler

BOT_TOKEN = "7376191947:AAEt28J_D-JKvGmAOIh6s0lNzCGdiHe1GpQ"

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam_handler))

app.run_polling()
