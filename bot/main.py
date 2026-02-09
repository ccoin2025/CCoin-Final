from telegram.ext import ApplicationBuilder, MessageHandler, filters
from anti_spam import anti_spam_handler


def main():
   app = ApplicationBuilder().token("7376191947:AAEt28J_D-JKvGmAOIh6s0lNzCGdiHe1GpQ").build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam_handler))

    print("🤖 Anti-Spam Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
