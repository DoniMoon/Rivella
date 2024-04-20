import logging
import os
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from analyse_paper import parse_pdf, get_sample_reviews, get_openai_client

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
openai_client = get_openai_client()


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! Send me your paper pdf to get reviews!",
        reply_markup=ForceReply(selective=True),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("We will generate review for your paper. Reviews will be generated when you upload your pdf.")


async def attachment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo user attachment."""
    attachment_file = await update.message.document.get_file()
    # download pdf and send back
    tmp_file = "attachment.pdf"
    await attachment_file.download_to_drive(tmp_file)
    await update.message.reply_text("Start analysing...")
    client = get_openai_client()
    summary, keyword, assistant, file_id = parse_pdf(client, tmp_file)
    await update.message.reply_text(f"Collecting review examples related to '{summary}', and the keyword '{keyword}'.")
    reviews, pdfs = get_sample_reviews(summary=summary, keyword=keyword)
    #XXX kmkim: write temp*.pdf files
    for i, pdf in enumerate(pdfs):
        with open(f"temp{i}.pdf", "wb") as f:
            f.write(pdf)
    await update.message.reply_text("Generating reviews with examples...")

 #   await update.message.reply_document(tmp_file, caption=f"Thanks.")

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(os.environ.get('TELEGRAM_KEY')).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # on non command i.e message - echo the message on Telegram
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_handler(MessageHandler(filters.ATTACHMENT & ~filters.COMMAND, attachment, block=True))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
