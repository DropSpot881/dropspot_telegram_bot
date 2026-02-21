"""Cart handler — view cart, checkout flow."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from bot import models
from bot.utils import format_price, DELIVERY_LABEL, DELIVERY_EMOJI, PAYMENT_LABEL, hdr, SEP, back_btn
from bot.config import SHOP_NAME

CHOOSING_DELIVERY, ENTERING_ADDRESS, CHOOSING_PAYMENT, CONFIRMING = range(4)


async def cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    cart = await models.get_cart(user_id)
    if not cart:
        await query.edit_message_text(
            f"{hdr('🛍', 'Your Cart')}\n\n"
            "Your cart is empty! 🛒\n"
            "Browse the shop to add items.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Shop", callback_data="shop")],
                [back_btn()],
            ]),
        )
        return

    total = 0
    lines = [f"{hdr('🛍', 'Your Cart')}\n"]
    buttons = []
    for i, item in enumerate(cart, 1):
        sub = item["price"] * item["quantity"]
        total += sub
        lines.append(f"*{i}.* {item['name']}\n    {item['quantity']}x · {format_price(item['price'])} = *{format_price(sub)}*")
        buttons.append([
            InlineKeyboardButton(f"🗑 {item['name']}", callback_data=f"rmcart_{item['product_id']}")
        ])

    lines.append(f"\n{SEP}\n💰 *Total: {format_price(total)}*")

    buttons.append([
        InlineKeyboardButton("🧹 Clear", callback_data="clear_cart"),
        InlineKeyboardButton("✅ Checkout", callback_data="checkout_start"),
    ])
    buttons.append([InlineKeyboardButton("🛒 Continue Shopping", callback_data="shop")])
    buttons.append([back_btn()])

    await query.edit_message_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def remove_from_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    product_id = int(query.data.split("_")[1])
    await models.remove_from_cart(user_id, product_id)
    await query.answer("🗑 Removed!")
    await cart_callback(update, context)


async def clear_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await models.clear_cart(query.from_user.id)
    await query.answer("🧹 Cleared!")
    await query.edit_message_text(
        f"{hdr('🧹', 'Cart Cleared')}\n\nReady to shop again? 🛒",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Shop", callback_data="shop")],
            [back_btn()],
        ]),
    )


# ── Checkout Flow ──────────────────────────────────────────

async def checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    cart = await models.get_cart(user_id)
    if not cart:
        await query.edit_message_text("🛍 Cart is empty!")
        return ConversationHandler.END

    # 1. Determine common delivery methods
    # We need to intersection allowed_delivery_methods from all vendors in the cart
    vendor_ids = set()
    for item in cart:
        # We need to fetch the product to get the vendor info
        prod = await models.get_product(item["product_id"])
        if prod and prod["vendor_id"]:
            vendor_ids.add(prod["vendor_id"])
    
    # Start with all possible methods
    common_methods = {"dead_drop", "pickup", "post", "today"}
    
    for v_id in vendor_ids:
        # This is a bit inefficient (multiple DB calls), but simple for now
        # We need to get vendor data
        db = await models.get_db()
        cursor = await db.execute("SELECT allowed_delivery_methods FROM vendors WHERE id = ?", (v_id,))
        row = await cursor.fetchone()
        await db.close()
        
        if row:
            v_methods = {m.strip() for m in (row["allowed_delivery_methods"] or "").split(",") if m.strip()}
            common_methods = common_methods.intersection(v_methods)
        else:
            # If vendor not found or no methods set, assume none
            common_methods = set()

    if not common_methods:
        await query.edit_message_text(
            "❌ *No Common Delivery Methods*\n\n"
            "The items in your cart come from vendors who don't share any delivery methods. "
            "Please order them separately.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[back_btn("🛒 Back to Cart", "cart")]])
        )
        return ConversationHandler.END

    total = sum(i["price"] * i["quantity"] for i in cart)
    context.user_data["checkout_items"] = [
        {"product_id": i["product_id"], "name": i["name"],
         "quantity": i["quantity"], "price": i["price"]}
        for i in cart
    ]
    context.user_data["checkout_total"] = total

    text = (
        f"{hdr('💳', 'Checkout')}\n\n"
        f"💰 Total: *{format_price(total)}*\n\n"
        f"*Step 1* — Delivery method 👇"
    )

    buttons = []
    # Map back to labels
    for m in ["dead_drop", "pickup", "post", "today"]:
        if m in common_methods:
            buttons.append([InlineKeyboardButton(f"{DELIVERY_EMOJI[m]} {DELIVERY_LABEL[m]}", callback_data=f"delivery_{m}")])
    
    buttons.append([InlineKeyboardButton("✖ Cancel", callback_data="checkout_cancel")])
    
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return CHOOSING_DELIVERY


async def delivery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("delivery_", "")
    context.user_data["delivery_method"] = method

    if method in ("post", "today"): # These definitely need an address
        emoji = DELIVERY_EMOJI.get(method, "📦")
        await query.edit_message_text(
            f"{hdr('📬', 'Address')}\n\n"
            f"{emoji} {DELIVERY_LABEL[method]}\n\n"
            f"*Step 2* — Type your address 👇\n\n"
            "_Street, number, city, postal code_",
            parse_mode="Markdown",
        )
        return ENTERING_ADDRESS
    else: # dead_drop or pickup - skip address
        context.user_data["address"] = ""
        return await show_payment_selection(query, context)


async def address_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()
    if len(address) < 5:
        await update.message.reply_text("❌ Too short. Enter full details:")
        return ENTERING_ADDRESS

    context.user_data["address"] = address
    buttons = [
        [InlineKeyboardButton("💵 Cash", callback_data="pay_cash")],
        [InlineKeyboardButton("✖ Cancel", callback_data="checkout_cancel")],
    ]
    await update.message.reply_text(
        f"{hdr('💳', 'Payment')}\n\n"
        f"📬 Details saved ✓\n\n"
        "*Step 3* — Payment method 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return CHOOSING_PAYMENT


async def show_payment_selection(query, context):
    delivery = context.user_data.get("delivery_method", "dead_drop")
    emoji = DELIVERY_EMOJI.get(delivery, "📍")
    buttons = [
        [InlineKeyboardButton("💵 Cash", callback_data="pay_cash")],
        [InlineKeyboardButton("✖ Cancel", callback_data="checkout_cancel")],
    ]
    await query.edit_message_text(
        f"{hdr('💳', 'Payment')}\n\n"
        f"{emoji} {DELIVERY_LABEL[delivery]} ✓\n\n"
        "*Step 2* — Payment method 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return CHOOSING_PAYMENT


async def payment_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("pay_", "")
    context.user_data["payment_method"] = method

    delivery = context.user_data["delivery_method"]
    total = context.user_data["checkout_total"]
    address = context.user_data.get("address", "")
    items = context.user_data["checkout_items"]

    d_emoji = DELIVERY_EMOJI.get(delivery, "📍")
    lines = [f"{hdr('📋', 'Order Summary')}\n"]
    for i, item in enumerate(items, 1):
        lines.append(f"*{i}.* {item['name']} ×{item['quantity']} = *{format_price(item['price'] * item['quantity'])}*")

    lines.append(f"\n{SEP}")
    lines.append(f"💰 *Total: {format_price(total)}*\n")
    lines.append(f"{d_emoji} {DELIVERY_LABEL[delivery]}")
    lines.append(f"💳 {PAYMENT_LABEL[method]}")
    if address:
        lines.append(f"📬 {address}")
    lines.append(f"\nConfirm your order? 👇")

    buttons = [
        [InlineKeyboardButton("✅ CONFIRM", callback_data="checkout_confirm")],
        [InlineKeyboardButton("✖ Cancel", callback_data="checkout_cancel")],
    ]
    await query.edit_message_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return CONFIRMING


async def checkout_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    delivery = context.user_data["delivery_method"]
    payment = context.user_data["payment_method"]
    address = context.user_data.get("address", "")
    total = context.user_data["checkout_total"]
    items = context.user_data["checkout_items"]

    order_id = await models.create_order(
        user_id=user.id,
        username=user.username or user.first_name,
        delivery_method=delivery,
        payment_method=payment,
        address=address,
        total=total,
        items=items,
    )
    await models.clear_cart(user.id)

    # What happens next — delivery-aware
    if delivery == "dead_drop":
        next_info = (
            "\n📍 *What's next?*\n"
            "A secret pickup location will be\n"
            "assigned after confirmation.\n"
            "⏳ Please wait for a message!"
        )
    elif delivery == "today":
        next_info = (
            "\n🚚 *What's next?*\n"
            "Being processed for same-day\n"
            "delivery. ⏳ We'll notify you\n"
            "when it's on the way!"
        )
    elif delivery == "pickup":
        next_info = (
            "\n🤝 *What's next?*\n"
            "The vendor will contact you\n"
            "to arrange the pick-up point.\n"
            "⏳ Please wait for a message!"
        )
    else:
        next_info = (
            "\n📦 *What's next?*\n"
            "Your order will be shipped.\n"
            "⏳ We'll notify you when\n"
            "it's dispatched!"
        )

    # Payment instructions - Cash only
    pay_text = (
        "\n💵 Pay *cash* on delivery/pickup.\n"
        "Tap *Confirm* to notify us 👇"
    )
    confirm_btn = InlineKeyboardButton("✅ Confirm", callback_data=f"ipaid_{order_id}")

    buttons = [
        [confirm_btn],
        [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
        [back_btn()],
    ]

    await query.edit_message_text(
        f"✅ *Order #{order_id} placed!*\n"
        f"{SEP}"
        f"{pay_text}"
        f"{next_info}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    # Notify admins
    from bot.config import ADMIN_IDS
    d_emoji = DELIVERY_EMOJI.get(delivery, "📍")
    admin_text = (
        f"🔔 *New Order #{order_id}*\n{SEP}\n\n"
        f"👤 @{user.username or user.first_name} (`{user.id}`)\n"
        f"{d_emoji} {DELIVERY_LABEL[delivery]}\n"
        f"💳 {PAYMENT_LABEL[payment]}\n"
        f"💰 *{format_price(total)}*\n"
    )
    if address:
        admin_text += f"📬 {address}\n"
    admin_text += "\n"
    for i in items:
        admin_text += f"• {i['name']} ×{i['quantity']} = {format_price(i['price'] * i['quantity'])}\n"

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=admin_text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View", callback_data=f"admin_order_{order_id}")]
                ]),
            )
        except Exception:
            pass

    context.user_data.clear()
    return ConversationHandler.END


async def i_paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[1])

    await models.mark_order_paid(order_id)

    await query.edit_message_text(
        f"💰 *Payment Noted!*\n\n"
        f"Order #{order_id}\n\n"
        "Our team has been notified. ✓\n"
        "You'll get delivery details once\n"
        "confirmed. ⏳",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
            [back_btn()],
        ]),
    )

    from bot.config import ADMIN_IDS
    order = await models.get_order(order_id)
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"💰 *Payment — Order #{order_id}*\n{SEP}\n\n"
                    f"👤 @{order['username']} (`{order['user_id']}`)\n"
                    f"💰 *{format_price(order['total'])}*\n"
                    f"💳 {PAYMENT_LABEL[order['payment_method']]}\n\n"
                    "Verify and confirm ⬇️"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Confirm", callback_data=f"admin_confirm_{order_id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"admin_cancel_{order_id}"),
                    ],
                    [InlineKeyboardButton("💬 Chat", callback_data=f"orderchat_{order_id}")]
                ]),
            )
        except Exception:
            pass


async def checkout_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Cancelled")
    context.user_data.clear()
    from bot.utils import main_menu_keyboard
    
    # Need to check if user is vendor for proper menu
    is_vendor = await models.get_vendor_by_user(query.from_user.id)
    if is_vendor:
        from bot.utils import vendor_dashboard_keyboard
        markup = vendor_dashboard_keyboard(bool(is_vendor["is_active"]))
    else:
        # Get notification status
        user_db = await models.get_user(query.from_user.id)
        notif_enabled = bool(user_db["notifications_enabled"]) if user_db else True
        markup = main_menu_keyboard(notif_enabled)

    await query.edit_message_text(
        "✖ *Checkout cancelled*\n\n"
        "Your cart is still saved. 🛒",
        parse_mode="Markdown",
        reply_markup=markup,
    )
    return ConversationHandler.END


def get_checkout_conversation_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(checkout_start, pattern=r"^checkout_start$"),
        ],
        states={
            CHOOSING_DELIVERY: [
                CallbackQueryHandler(delivery_chosen, pattern=r"^delivery_"),
                CallbackQueryHandler(checkout_cancel, pattern=r"^checkout_cancel$"),
            ],
            ENTERING_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, address_entered),
            ],
            CHOOSING_PAYMENT: [
                CallbackQueryHandler(payment_chosen, pattern=r"^pay_"),
                CallbackQueryHandler(checkout_cancel, pattern=r"^checkout_cancel$"),
            ],
            CONFIRMING: [
                CallbackQueryHandler(checkout_confirm, pattern=r"^checkout_confirm$"),
                CallbackQueryHandler(checkout_cancel, pattern=r"^checkout_cancel$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(checkout_cancel, pattern=r"^checkout_cancel$"),
        ],
        per_message=False,
    )
