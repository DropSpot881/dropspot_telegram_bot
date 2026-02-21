"""Order chat handler — messaging between customer and admin/vendor."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from bot import models
from bot.utils import hdr, SEP, is_admin
from bot.config import ADMIN_IDS

# States
WAITING_FOR_MESSAGE = 1

async def chat_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split("_")[1])
    context.user_data["chat_order_id"] = order_id
    
    messages = await models.get_order_messages(order_id)
    history = ""
    if messages:
        history = "\n\n*Recent History:*\n"
        for m in messages[-5:]: # Show last 5
            sender = "User" if m["sender_id"] not in ADMIN_IDS else "Shop"
            history += f"• *{sender}:* {m['text']}\n"

    await query.edit_message_text(
        f"{hdr('💬', 'Order Chat')}\n\n"
        f"Order: *#{order_id}*\n"
        f"Status: Please send your message below. ✍️\n"
        f"{history}\n"
        f"{SEP}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖ Cancel", callback_data=f"vieworder_{order_id}")]])
    )
    return WAITING_FOR_MESSAGE

async def chat_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    order_id = context.user_data.get("chat_order_id")
    text = update.message.text.strip()
    
    if not order_id or not text:
        return ConversationHandler.END

    # Save message
    await models.add_order_message(order_id, user.id, text)
    
    # Notify recipient
    order = await models.get_order(order_id)
    if not order:
        return ConversationHandler.END
        
    sender_is_admin = is_admin(user.id)
    
    if sender_is_admin:
        # Notify customer
        customer_id = order["user_id"]
        msg_text = (
            f"💬 *New message from Shop (Order #{order_id}):*\n\n"
            f"{text}\n\n"
            "You can reply from the Order menu."
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("📦 View Order", callback_data=f"vieworder_{order_id}")]])
        try:
            await context.bot.send_message(customer_id, msg_text, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            pass
    else:
        # Notify Admins
        msg_text = (
            f"💬 *New chat for Order #{order_id}:*\n"
            f"From: @{user.username or user.id}\n\n"
            f"{text}"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("📋 View Order", callback_data=f"admin_vorder_{order_id}")]])
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(admin_id, msg_text, parse_mode="Markdown", reply_markup=markup)
            except Exception:
                pass

    await update.message.reply_text(
        "✅ Message sent!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ Back to Order", callback_data=f"vieworder_{order_id}")]])
    )
    return ConversationHandler.END

def get_chat_conversation_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(chat_start_callback, pattern=r"^orderchat_"),
        ],
        states={
            WAITING_FOR_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message_handler),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(chat_start_callback, pattern=r"^orderchat_"),
        ],
        per_message=False,
    )
