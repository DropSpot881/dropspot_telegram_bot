"""Shop handler — browse categories, products, add to cart."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot import models
from bot.utils import format_price, hdr, SEP, back_btn


async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Determine fulfillment filter from callback_data or user_data
    if query.data == "on_post":
        context.user_data["fulfillment_pref"] = "post"
    elif query.data == "on_f2f":
        context.user_data["fulfillment_pref"] = "local" # maps to deaddrop/pickup/delivery
    
    pref = context.user_data.get("fulfillment_pref")
    
    # Define method groups
    filter_vals = None
    if pref == "post":
        filter_vals = ["post"]
    elif pref == "local":
        filter_vals = ["dead_drop", "pickup", "today"] # today=delivery

    active_count = await models.get_active_vendors_count()
    if active_count == 0:
        await query.edit_message_text(
            f"{hdr('🏪', 'Shop')}\n\n"
            "🔴 *Shop Closed*\n\n"
            "There are currently no active plugs. Check back later! ⏳",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[back_btn()]]),
        )
        return

    categories = await models.get_categories(filter_methods=filter_vals)

    if not categories:
        await query.edit_message_text(
            f"{hdr('🏪', 'Shop')}\n\n"
            "🔄 No products yet — check back soon!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[back_btn()]]),
        )
        return

    text = f"{hdr('🏪', 'Shop')}\n\n"
    buttons = []
    for cat in categories:
        prods = await models.get_products_by_category(cat['id'])
        buttons.append([
            InlineKeyboardButton(
                f"📂 {cat['name']} ({len(prods)})",
                callback_data=f"cat_{cat['id']}"
            )
        ])
    buttons.append([back_btn()])

    await query.edit_message_text(
        text + "Pick a category 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category_id = int(query.data.split("_")[1])

    pref = context.user_data.get("fulfillment_pref")
    filter_vals = None
    if pref == "post":
        filter_vals = ["post"]
    elif pref == "local":
        filter_vals = ["dead_drop", "pickup", "today"]
    
    products = await models.get_products_by_category(category_id, filter_methods=filter_vals)
    if not products:
        await query.edit_message_text(
            f"{hdr('📭', 'Empty')}\n\nNo products here yet.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩ Shop", callback_data="shop")]
            ]),
        )
        return

    lines = [f"{hdr('📦', 'Products')}\n"]
    buttons = []
    for p in products:
        stock = "🟢" if p["in_stock"] else "🔴"
        vendor_tag = f" 🏪 {p['vendor_name']}" if p["vendor_name"] else ""
        lines.append(f"{stock} {p['name']} — *{format_price(p['price'])}*{vendor_tag}")
        buttons.append([
            InlineKeyboardButton(
                f"{p['name']} • {format_price(p['price'])}",
                callback_data=f"prod_{p['id']}",
            )
        ])
    buttons.append([InlineKeyboardButton("↩ Shop", callback_data="shop")])

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    # Handle both 'prod_123' and 'qty_inc_123' / 'qty_dec_123'
    if parts[0] == "prod":
        product_id = int(parts[1])
    else:
        product_id = int(parts[2])

    product = await models.get_product(product_id)
    if not product:
        await query.edit_message_text("❌ Product not found.")
        return

    stock = "🟢 In Stock" if product["in_stock"] else "🔴 Out of Stock"
    vendor_info = ""
    if product["vendor_name"]:
        vendor_info = f"🏪 *Vendor:* {product['vendor_name']}\n"

    qty = context.user_data.get(f"qty_{product_id}", 1)

    text = (
        f"🏷 *{product['name']}*\n\n"
        f"{product['description'] or 'No description.'}\n\n"
        f"{vendor_info}"
        f"💰 *{format_price(product['price'])}* (each)\n"
        f"{stock}\n"
        f"🔢 *Quantity:* {qty}"
    )

    buttons = []
    if product["in_stock"]:
        buttons.append([
            InlineKeyboardButton("➖", callback_data=f"qty_dec_{product_id}"),
            InlineKeyboardButton(f"{qty}", callback_data="none"),
            InlineKeyboardButton("➕", callback_data=f"qty_inc_{product_id}"),
        ])
        buttons.append([
            InlineKeyboardButton("🛒 Add to Cart", callback_data=f"addcart_{product_id}")
        ])
    buttons.append([
        InlineKeyboardButton("↩ Back", callback_data=f"cat_{product['category_id']}"),
        InlineKeyboardButton("🛍 Cart", callback_data="cart"),
    ])

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def quantity_change_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    action = parts[1]
    product_id = int(parts[2])
    
    qty_key = f"qty_{product_id}"
    qty = context.user_data.get(qty_key, 1)
    
    if action == "inc":
        qty += 1
    elif action == "dec" and qty > 1:
        qty -= 1
        
    context.user_data[qty_key] = qty
    return await product_callback(update, context)


async def add_to_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    product_id = int(query.data.split("_")[1])
    
    qty_key = f"qty_{product_id}"
    quantity = context.user_data.get(qty_key, 1)

    product = await models.get_product(product_id)
    await models.add_to_cart(user_id, product_id, quantity)

    name = product["name"] if product else "Item"
    await query.answer(f"✅ {quantity}x {name} added!", show_alert=True)
    
    # Reset quantity for next time
    context.user_data[qty_key] = 1
    return await product_callback(update, context)


