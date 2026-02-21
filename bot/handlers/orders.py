"""Orders handler — view order history and details."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot import models
from bot.utils import (
    format_price, STATUS_EMOJI, STATUS_LABEL,
    DELIVERY_LABEL, DELIVERY_EMOJI, PAYMENT_LABEL,
    hdr, SEP, back_btn,
)


def progress_bar(status: str) -> str:
    """Compact visual progress indicator."""
    steps = {"pending_payment": 0, "paid": 1, "confirmed": 2, "shipped": 3, "completed": 4, "cancelled": -1}
    pos = steps.get(status, 0)
    if pos == -1:
        return "🔴 Cancelled"
    icons = ["📝", "💰", "✅", "🚚", "🏁"]
    parts = []
    for i, icon in enumerate(icons):
        if i <= pos:
            parts.append(icon)
        else:
            parts.append("⬜")
    return " → ".join(parts)


async def my_orders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    orders = await models.get_user_orders(user_id)
    if not orders:
        await query.edit_message_text(
            f"{hdr('📦', 'My Orders')}\n\n"
            "No orders yet! 🛒\nBrowse the shop to get started.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Shop", callback_data="shop")],
                [back_btn()],
            ]),
        )
        return

    lines = [f"{hdr('📦', 'My Orders')}\n"]
    buttons = []
    for o in orders:
        emoji = STATUS_EMOJI.get(o["status"], "❓")
        label = STATUS_LABEL.get(o["status"], o["status"])
        lines.append(f"{emoji} *#{o['id']}* · {format_price(o['total'])} · {label}")
        buttons.append([
            InlineKeyboardButton(f"#{o['id']} — {label}", callback_data=f"vieworder_{o['id']}"),
            InlineKeyboardButton("💬 Chat", callback_data=f"orderchat_{o['id']}")
        ])

    buttons.append([back_btn()])
    await query.edit_message_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def view_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[1])

    order = await models.get_order(order_id)
    if not order:
        await query.edit_message_text("❌ Order not found.")
        return

    if order["user_id"] != query.from_user.id:
        from bot.utils import is_admin
        if not is_admin(query.from_user.id):
            await query.edit_message_text("⛔ Access denied.")
            return

    items = await models.get_order_items(order_id)
    emoji = STATUS_EMOJI.get(order["status"], "❓")
    d_emoji = DELIVERY_EMOJI.get(order["delivery_method"], "📦")

    lines = [
        f"📋 <b>Order #{order_id}</b>\n{SEP}\n",
        progress_bar(order["status"]),
        "",
        f"{emoji} {STATUS_LABEL.get(order['status'], order['status'])}",
        f"{d_emoji} {DELIVERY_LABEL.get(order['delivery_method'], '')}",
        f"💳 {PAYMENT_LABEL.get(order['payment_method'], '')}",
        f"💰 <b>{format_price(order['total'])}</b>",
    ]

    if order["address"]:
        lines.append(f"📬 <i>{order['address']}</i>")

    lines.append(f"\n<b>Items:</b>")
    for item in items:
        lines.append(f"• {item['product_name']} ×{item['quantity']} = <b>{format_price(item['price'] * item['quantity'])}</b>")

    # Dead drop location
    if order["status"] == "confirmed" and order["delivery_method"] == "dead_drop" and order["location_id"]:
        location = await models.get_location(order["location_id"])
        if location:
            lines.append(f"\n📍 <b>PICKUP LOCATION</b>\n{SEP}")
            lines.append(f"📌 <b>{location['name']}</b>")
            if location["maps_url"]:
                lines.append(f'🗺 <a href="{location["maps_url"]}">Open in Maps</a>')
            else:
                lines.append(f"🗺 {location['address']}")
            
            if location["description"]:
                lines.append(f"ℹ️ <i>{location['description']}</i>")
            if order["pickup_expires_at"]:
                lines.append(f"⏰ Expires: <b>{order['pickup_expires_at']}</b>")
                lines.append("⚠️ <i>Pick up before expiry!</i>")

    # Shipping status
    if order["status"] == "shipped" and order["delivery_method"] in ("post", "today"):
        lines.append(f"\n🚀 <b>On its way!</b> 📬")
    elif order["status"] == "confirmed" and order["delivery_method"] in ("post", "today"):
        lines.append(f"\n📦 <i>Being prepared...</i>")

    buttons = []
    if order["status"] == "pending_payment":
        if order["payment_method"] == "crypto":
            from bot.config import CRYPTO_WALLET_BTC, CRYPTO_WALLET_ETH
            lines.append(f"\n₿ <b>Pay to:</b>")
            lines.append(f"BTC: <code>{CRYPTO_WALLET_BTC}</code>")
            lines.append(f"ETH: <code>{CRYPTO_WALLET_ETH}</code>")
        buttons.append([
            InlineKeyboardButton("💸 I Have Paid", callback_data=f"ipaid_{order_id}")
        ])

    chat_btn = [InlineKeyboardButton("💬 Chat Vendor", callback_data=f"orderchat_{order_id}")]
    
    # Prioritize chat button at the top for active orders
    if order["status"] in ("confirmed", "shipped", "paid"):
        buttons.insert(0, chat_btn)
    else:
        buttons.append(chat_btn)
    buttons.append([InlineKeyboardButton("↩ Orders", callback_data="my_orders")])
    buttons.append([back_btn()])

    # Review button if completed
    if order["status"] == "completed":
        buttons.insert(0, [InlineKeyboardButton("⭐ Leave a Review", callback_data=f"review_{order_id}")])

    await query.edit_message_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def buyer_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    order_id = int(query.data.split("_")[1])
    
    order = await models.get_order(order_id)
    if not order or order["user_id"] != query.from_user.id:
        await query.answer("❌ Not authorized.")
        return
        
    await models.cancel_order(order_id)
    await query.answer("🔴 Order cancelled.", show_alert=True)
    return await view_order_callback(update, context)


async def im_here_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    order_id = int(query.data.split("_")[1])
    
    order = await models.get_order(order_id)
    if not order: return
    
    # Notify admin/vendor
    msg = f"📍 <b>Order #{order_id}</b>\nBuyer has arrived at the meeting point! 🤝"
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏃 On the way", callback_data=f"vonway_{order_id}")
    ]])
    from bot.config import ADMIN_IDS
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, msg, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass
            
    await query.answer("🔔 Vendor notified! Please wait.", show_alert=True)


async def vendor_on_way_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    order_id = int(query.data.split("_")[1])
    
    order = await models.get_order(order_id)
    if not order:
        await query.answer("Order not found.")
        return
        
    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=f"🏃 <b>Vendor is on the way!</b>\nOrder #{order_id}\n\nPlease stay at the meeting point. 🤝",
            parse_mode="HTML"
        )
        await query.answer("✅ Buyer notified!")
        await query.edit_message_text(
            query.message.text + "\n\n✅ <i>You notified the buyer that you are on the way.</i>",
            parse_mode="HTML"
        )
    except Exception:
        await query.answer("❌ Could not notify buyer.")
