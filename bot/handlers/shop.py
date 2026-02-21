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
    product_id = int(parts[1])

    product = await models.get_product(product_id)
    if not product:
        await query.edit_message_text("❌ Product not found.")
        return

    variants = await models.get_product_variants(product_id)

    stock = "🟢 In Stock" if product["in_stock"] else "🔴 Out of Stock"
    vendor_info = ""
    if product["vendor_name"]:
        vendor_info = f"🏪 *Vendor:* {product['vendor_name']}\n"

    price_info = f"💰 Starting from *{format_price(product['price'])}*\n" if not variants else ""

    text = (
        f"🏷 *{product['name']}*\n\n"
        f"{product['description'] or 'No description.'}\n\n"
        f"{vendor_info}"
        f"{price_info}"
        f"{stock}\n\n"
        "✨ *Choose an option:* 👇"
    )

    buttons = []
    if product["in_stock"]:
        for v in variants:
            buttons.append([
                InlineKeyboardButton(f"🛒 {v['name']} — {format_price(v['price'])}", callback_data=f"addvar_{product_id}_{v['id']}")
            ])
    
    buttons.append([
        InlineKeyboardButton("↩ Back", callback_data=f"cat_{product['category_id']}"),
        InlineKeyboardButton("🛍 Cart", callback_data="cart"),
    ])

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def add_variant_to_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    product_id = int(parts[1])
    variant_id = int(parts[2])
    
    user_id = query.from_user.id
    await models.add_to_cart(user_id, product_id, variant_id, 1)
    
    await query.answer("✅ Added to cart!")


