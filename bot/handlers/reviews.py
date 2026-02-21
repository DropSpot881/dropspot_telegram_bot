"""Review handler — buyers can leave anonymous reviews after orders are completed."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters,
)
from bot import models
from bot.utils import hdr, SEP

# Conversation states
WAITING_RATING, WAITING_COMMENT = range(2)

async def review_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[1])
    
    order = await models.get_order(order_id)
    if not order or order["status"] != "completed":
        await query.edit_message_text("❌ Review only available for completed orders.")
        return ConversationHandler.END

    context.user_data["review_order_id"] = order_id
    
    buttons = []
    # 1-5 Star buttons
    row = []
    for i in range(1, 6):
        row.append(InlineKeyboardButton(f"{i} ⭐", callback_data=f"rev_rate_{i}"))
    buttons.append(row)
    buttons.append([InlineKeyboardButton("✖ Cancel", callback_data="rev_cancel")])

    await query.edit_message_text(
        f"{hdr('⭐', 'Make Review')}\n\n"
        f"Order *#{order_id}*\n\n"
        "How would you rate your experience? 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return WAITING_RATING


async def review_rating_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rating = int(query.data.split("_")[2])
    context.user_data["review_rating"] = rating
    
    await query.edit_message_text(
        f"{hdr('📝', 'Comment')}\n\n"
        f"Rating: {rating} ⭐\n\n"
        "Now, please write a short anonymous review about the deal / product (optional, or type /skip) ✍️",
        parse_mode="Markdown"
    )
    return WAITING_COMMENT


async def review_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get("review_order_id")
    rating = context.user_data.get("review_rating", 5)
    comment = update.message.text.strip() if update.message.text != "/skip" else ""
    
    order = await models.get_order(order_id)
    items = await models.get_order_items(order_id)
    
    # Associate review with the first product in the order for now
    product_id = items[0]["product_id"] if items else None
    
    await models.add_review(
        order_id=order_id,
        user_id=update.effective_user.id,
        product_id=product_id,
        rating=rating,
        comment=comment
    )
    
    await update.message.reply_text("✅ Thank you for your anonymous review! Your feedback helps the community. 🙏")
    
    context.user_data.pop("review_order_id", None)
    context.user_data.pop("review_rating", None)
    return ConversationHandler.END


async def review_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Review cancelled.")
    await query.edit_message_text("❌ Review cancelled.")
    return ConversationHandler.END


def get_review_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(review_start, pattern=r"^review_\d+$")],
        states={
            WAITING_RATING: [CallbackQueryHandler(review_rating_chosen, pattern=r"^rev_rate_\d+$")],
            WAITING_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, review_save),
                MessageHandler(filters.COMMAND & filters.Regex(r"^/skip$"), review_save),
            ],
        },
        fallbacks=[CallbackQueryHandler(review_cancel, pattern=r"^rev_cancel$")],
        per_chat=True,
    )
