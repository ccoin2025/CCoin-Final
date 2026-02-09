from telegram.ext import Application, MessageHandler, filters
from anti_spam import anti_spam_handler

BOT_TOKEN = "7376191947:AAEt28J_D-JKvGmAOIh6s0lNzCGdiHe1GpQ"

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam_handler)
    )
    print("BOT STARTED")
    print("🤖 Anti-Spam Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
