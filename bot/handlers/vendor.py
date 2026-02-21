"""Vendor handler — /active and /vendor commands."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler,
)
from bot import models
from bot.utils import hdr, SEP, back_btn, format_price


# Conversation states
(
    VENDOR_MENU, 
    EDIT_DELIVERY_INFO, 
    ADD_PROD_CAT, 
    ADD_PROD_NAME, 
    ADD_PROD_DESC, 
    ADD_PROD_PRICE, 
    ADD_PROD_METHODS, 
    ADD_CAT_NAME,
    VND_EDITP_PICK,
    VND_EDITP_MENU,
    VND_EDITP_NAME,
    VND_EDITP_DESC,
    VND_EDITP_PRICE,
    VND_EDITP_METHODS,
    VND_CAT_MGMT,
    VND_RENAME_CAT_PICK,
    VND_RENAME_CAT_NAME
) = range(17)

# Unified delivery keys (aligned with checkout)
DELIVERY_METHODS = {
    "dead_drop": "📍 Deaddrop",
    "pickup": "🤝 Pick-up",
    "post": "📦 Post",
    "today": "🚚 Delivery"
}


async def vendor_check(update: Update):
    user_id = update.effective_user.id
    vendor = await models.get_vendor_by_user(user_id)
    if not vendor:
        if update.message:
            await update.message.reply_text("⛔ You are not registered as a vendor.")
        elif update.callback_query:
            await update.callback_query.answer("⛔ Access denied.", show_alert=True)
        return None
    return dict(vendor) if vendor else None


async def notify_users_vendor_active(context: ContextTypes.DEFAULT_TYPE, vendor_name: str):
    """Notify all users who have notifications enabled."""
    user_ids = await models.get_users_for_notifications()
    text = (
        f"🔌 *THE PLUG IS ACTIVE!*\n{SEP}\n\n"
        f"🏪 *{vendor_name}* is now online and accepting orders! ✅\n\n"
        "🛒 Check the shop to see what's in stock."
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Open Shop", callback_data="shop")]])
    
    count = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
            count += 1
        except Exception:
            continue
    return count


async def active_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/active command to toggle daily active status."""
    vendor = await vendor_check(update)
    if not vendor:
        return

    # Toggle active for 24 hours
    is_active = not bool(vendor["is_active"])
    await models.set_vendor_active(vendor["user_id"], is_active)
    
    if is_active:
        await notify_users_vendor_active(context, vendor["display_name"])
    
    status = "🟢 ACTIVE" if is_active else "🔴 INACTIVE"
    text = f"📢 Vendor Status: {status}\n\n"
    if is_active:
        text += "Your products are now visible and users have been notified! ✅"
    else:
        text += "Your products are now hidden from the shop. ❌"

    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.answer(f"Status: {status}")
        from bot.handlers.start import start_command
        await start_command(update, context)


async def vendor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/vendor command to open vendor settings."""
    vendor = await vendor_check(update)
    if not vendor:
        return ConversationHandler.END

    status = "🟢 Active" if vendor["is_active"] else "🔴 Inactive"
    
    text = (
        f"{hdr('🏪', 'Vendor Panel')}\n\n"
        f"👤 *Display Name:* {vendor.get('display_name', 'Unknown')}\n"
        f"📍 *Status:* {status}\n\n"
        f"📝 *Delivery Details:*\n_{vendor.get('delivery_info') or 'Not set'}_"
    )

    buttons = [
        [InlineKeyboardButton("📦 Products", callback_data="vnd_products")],
        [InlineKeyboardButton("📂 Categories", callback_data="vnd_cat_mgmt")],
        [InlineKeyboardButton("✍️ Edit Delivery Info", callback_data="vnd_edit_delivery")],
        [InlineKeyboardButton("🔄 Toggle Active", callback_data="vnd_toggle_active")],
        [InlineKeyboardButton("↩ Dashboard", callback_data="main_menu")],
    ]

    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    
    return VENDOR_MENU


async def vnd_toggle_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    vendor = await vendor_check(update)
    if not vendor:
        return ConversationHandler.END

    is_active = not bool(vendor["is_active"])
    await models.set_vendor_active(vendor["user_id"], is_active)
    
    if is_active:
        await notify_users_vendor_active(context, vendor["display_name"])
    
    await query.answer(f"Status changed to {'Active' if is_active else 'Inactive'}")
    
    # Check if we should reload the start menu (dashboard) or the vendor panel
    if query.data == "toggle_notifs":
        from bot.handlers.start import start_command
        await start_command(update, context)
        return VENDOR_MENU

    return await vendor_command(update, context)


async def vnd_edit_delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{hdr('📝', 'Delivery Info')}\n\n"
        "Enter your delivery details / options ✍️\n\n"
        "_Example: Dead Drop in Kristiansand city center, Same day delivery available after 18:00..._",
        parse_mode="Markdown"
    )
    return EDIT_DELIVERY_INFO


async def vnd_edit_delivery_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    info = update.message.text.strip()
    
    await models.update_vendor_info(user_id, delivery_info=info)
    await update.message.reply_text("✅ Delivery info updated!")
    
    # Return to menu
    return await vendor_command(update, context)


# ── Vendor Product Management ─────────────────────────────

async def vnd_products_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    vendor = await vendor_check(update)
    if not vendor: return VENDOR_MENU

    products = await models.get_vendor_products(vendor["id"])
    
    text = f"{hdr('📦', 'My Listings')}\n\nManage your products:"
    buttons = []
    
    for p in products:
        stock = "🟢" if p["in_stock"] else "🔴"
        buttons.append([
            InlineKeyboardButton(f"{stock} {p['name']} — {format_price(p['price'])}", callback_data=f"vnd_togp_{p['id']}"),
        ])
        buttons.append([
            InlineKeyboardButton("✏️ Edit Details", callback_data=f"vnd_editp_{p['id']}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"vnd_delp_{p['id']}")
        ])
    
    buttons.append([InlineKeyboardButton("➕ Add Product", callback_data="vnd_addp_start")])
    buttons.append([InlineKeyboardButton("↩ Back", callback_data="vendor_panel_redirect")])
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return VENDOR_MENU


async def vnd_toggle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    prod_id = int(query.data.split("_")[2])
    
    p = await models.get_product(prod_id)
    if not p: return VENDOR_MENU
    
    new_stock = 0 if p["in_stock"] else 1
    await models.update_product(prod_id, in_stock=new_stock)
    
    await query.answer("Stock updated!")
    return await vnd_products_menu(update, context)


async def vnd_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    prod_id = int(query.data.split("_")[2])
    
    await models.delete_product(prod_id)
    
    await query.answer("Product deleted.")
    return await vnd_products_menu(update, context)


async def vnd_addp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cats = await models.get_all_categories()
    if not cats:
        await query.answer("No categories available! Contact admin.")
        # FALLBACK: Allow creating category here
        buttons = [[InlineKeyboardButton("✨ Create New Category", callback_data="vnd_ac_start")]]
        buttons.append([InlineKeyboardButton("✖ Cancel", callback_data="vnd_products")])
        await query.edit_message_text(f"{hdr('📂', 'Add Product')}\n\nNo categories found! Create one first:", reply_markup=InlineKeyboardMarkup(buttons))
        return ADD_PROD_CAT

    buttons = [[InlineKeyboardButton(c["name"], callback_data=f"vnd_ap_cat_{c['id']}")] for c in cats]
    buttons.append([InlineKeyboardButton("✨ Create New Category", callback_data="vnd_ac_start")])
    buttons.append([InlineKeyboardButton("✖ Cancel", callback_data="vnd_products")])
    
    await query.edit_message_text(
        f"{hdr('📦', 'Add Product')}\n\n*Step 1:* Choose Category 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return ADD_PROD_CAT


async def vnd_addp_name_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["vnd_addp_cat"] = int(query.data.split("_")[3])
    
    await query.edit_message_text(f"{hdr('📦', 'Add Product')}\n\n*Step 2:* Enter Product Name ✍️", parse_mode="Markdown")
    return ADD_PROD_NAME


async def vnd_addp_desc_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["vnd_addp_name"] = update.message.text.strip()
    await update.message.reply_text("*Step 3:* Enter Description ✍️", parse_mode="Markdown")
    return ADD_PROD_DESC


async def vnd_addp_price_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["vnd_addp_desc"] = update.message.text.strip()
    await update.message.reply_text("*Step 4:* Enter Price (e.g. `199`) ✍️", parse_mode="Markdown")
    return ADD_PROD_PRICE


async def vnd_addp_methods_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(",", "."))
        context.user_data["vnd_addp_price"] = price
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Enter a number:")
        return ADD_PROD_PRICE

    # Initial methods (all selected by default)
    context.user_data["vnd_addp_methods"] = ["dead_drop", "pickup", "post", "today"]
    
    return await vnd_addp_methods_render(update, context)


async def vnd_addp_methods_render(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected = context.user_data["vnd_addp_methods"]
    
    buttons = []
    for key, label in DELIVERY_METHODS.items():
        toggle = "✅" if key in selected else "❌"
        buttons.append([InlineKeyboardButton(f"{toggle} {label}", callback_data=f"vnd_ap_m_{key}")])
    
    buttons.append([InlineKeyboardButton("💾 Save Product", callback_data="vnd_ap_save")])
    buttons.append([InlineKeyboardButton("✖ Cancel", callback_data="vnd_products")])
    
    text = f"{hdr('📦', 'Add Product')}\n\n*Step 5:* Choose Delivery Options 👇"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    
    return ADD_PROD_METHODS


async def vnd_addp_method_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    method = query.data.replace("vnd_ap_m_", "")
    selected = context.user_data.get("vnd_addp_methods", ["dead_drop", "pickup", "post", "today"])
    
    if method in selected:
        if len(selected) > 1: # Must have at least one
            selected.remove(method)
    else:
        selected.append(method)
    
    context.user_data["vnd_addp_methods"] = selected
    await query.answer()
    return await vnd_addp_methods_render(update, context)


async def vnd_addp_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    vendor = await vendor_check(update)
    if not vendor: return ConversationHandler.END

    data = context.user_data
    methods = ",".join(data["vnd_addp_methods"])
    
    await models.add_product(
        category_id=data["vnd_addp_cat"],
        name=data["vnd_addp_name"],
        description=data["vnd_addp_desc"],
        price=data["vnd_addp_price"],
        vendor_id=vendor["id"],
        allowed_methods=methods
    )
    
    await query.answer("Product added successfully! 🎉")
    return await vnd_products_menu(update, context)


# ── Vendor Product Editing ─────────────────────────────────

async def vnd_editp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    prod_id = int(query.data.split("_")[2])
    p = await models.get_product(prod_id)
    if not p:
        await query.answer("Product not found.")
        return await vnd_products_menu(update, context)
    
    context.user_data["editp_id"] = prod_id
    
    text = (
        f"{hdr('✏️', 'Edit Product')}\n\n"
        f"*Name:* {p['name']}\n"
        f"*Price:* {format_price(p['price'])}\n"
        f"*Stock:* {'🟢 In Stock' if p['in_stock'] else '🔴 Out of Stock'}\n\n"
        "What would you like to edit?"
    )
    
    buttons = [
        [InlineKeyboardButton("📝 Edit Name", callback_data="evp_name")],
        [InlineKeyboardButton("✍️ Edit Description", callback_data="evp_desc")],
        [InlineKeyboardButton("💰 Edit Price", callback_data="evp_price")],
        [InlineKeyboardButton("🚚 Edit Delivery Options", callback_data="evp_methods")],
        [InlineKeyboardButton("↩ Back", callback_data="vnd_products")]
    ]
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return VND_EDITP_MENU


async def evp_name_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Enter new product name: ✍️")
    return VND_EDITP_NAME

async def evp_name_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    await models.update_product(context.user_data["editp_id"], name=name)
    await update.message.reply_text("✅ Name updated!")
    return await vnd_products_menu(update, context)

async def evp_desc_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Enter new description: ✍️")
    return VND_EDITP_DESC

async def evp_desc_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    await models.update_product(context.user_data["editp_id"], description=desc)
    await update.message.reply_text("✅ Description updated!")
    return await vnd_products_menu(update, context)

async def evp_price_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Enter new price: ✍️")
    return VND_EDITP_PRICE

async def evp_price_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(",", "."))
        await models.update_product(context.user_data["editp_id"], price=price)
        await update.message.reply_text("✅ Price updated!")
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Enter a number:")
        return VND_EDITP_PRICE
    return await vnd_products_menu(update, context)

async def evp_methods_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    prod_id = context.user_data["editp_id"]
    p = await models.get_product(prod_id)
    
    allowed_raw = p.get("allowed_delivery_methods", "dead_drop,pickup,post,today")
    if allowed_raw is None: allowed_raw = ""
    
    allowed_list = [m.strip() for m in allowed_raw.split(",") if m.strip()]
    
    buttons = []
    for key, label in DELIVERY_METHODS.items():
        toggle = "✅" if key in allowed_list else "❌"
        buttons.append([InlineKeyboardButton(f"{toggle} {label}", callback_data=f"evp_togm_{key}")])
    
    buttons.append([InlineKeyboardButton("💾 Finish", callback_data="vnd_products")])
    
    await query.edit_message_text(f"{hdr('🚚', 'Edit Options')}\n\nToggle delivery options for this product:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return VND_EDITP_METHODS

async def evp_methods_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    method = query.data.replace("evp_togm_", "")
    
    prod_id = context.user_data["editp_id"]
    p = await models.get_product(prod_id)
    
    allowed_raw = p.get("allowed_delivery_methods", "dead_drop,pickup,post,today")
    if allowed_raw is None: allowed_raw = ""
    
    allowed_list = [m.strip() for m in allowed_raw.split(",") if m.strip()]
    
    if method in allowed_list:
        if len(allowed_list) > 1: allowed_list.remove(method)
    else:
        allowed_list.append(method)
    
    await models.update_product(prod_id, allowed_delivery_methods=",".join(allowed_list))
    await query.answer(f"Updated {method}")
    return await evp_methods_menu(update, context)


# ── Vendor Category Management ─────────────────────────────

async def vnd_cat_mgmt_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cats = await models.get_all_categories()
    
    text = f"{hdr('📂', 'Categories')}\n\nManage product categories:"
    buttons = [
        [InlineKeyboardButton("➕ Add Category", callback_data="vnd_ac_start")],
        [InlineKeyboardButton("✏️ Rename Category", callback_data="vnd_ac_rename")],
        [InlineKeyboardButton("↩ Back", callback_data="vendor_panel_redirect")]
    ]
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return VND_CAT_MGMT


async def vnd_addcat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{hdr('📂', 'New Category')}\n\nEnter the name for the new category: ✍️",
        parse_mode="Markdown"
    )
    return ADD_CAT_NAME


async def vnd_addcat_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("❌ Name cannot be empty. Enter name:")
        return ADD_CAT_NAME
    
    try:
        await models.add_category(name)
        await update.message.reply_text(f"✅ Category *{name}* created!", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("❌ Error: Category might already exist.")
    
    return await vnd_cat_mgmt_menu(update, context)


async def vnd_rename_cat_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cats = await models.get_all_categories()
    buttons = [[InlineKeyboardButton(c["name"], callback_data=f"vrc_p_{c['id']}")] for c in cats]
    buttons.append([InlineKeyboardButton("↩ Back", callback_data="vnd_cat_mgmt")])
    
    await query.edit_message_text("Choose a category to rename: 👇", reply_markup=InlineKeyboardMarkup(buttons))
    return VND_RENAME_CAT_PICK


async def vnd_rename_cat_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["rename_cat_id"] = int(query.data.split("_")[2])
    
    await query.edit_message_text("Enter the new name for this category: ✍️")
    return VND_RENAME_CAT_NAME

async def vnd_rename_cat_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if name:
        await models.update_category(context.user_data["rename_cat_id"], name=name)
        await update.message.reply_text(f"✅ Category renamed to *{name}*!", parse_mode="Markdown")
    
    return await vnd_cat_mgmt_menu(update, context)


def get_vendor_conversation_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("vendor", vendor_command),
            CallbackQueryHandler(vendor_command, pattern=r"^vendor_panel_redirect$"),
        ],
        states={
            VENDOR_MENU: [
                CallbackQueryHandler(vnd_products_menu, pattern=r"^vnd_products$"),
                CallbackQueryHandler(vnd_cat_mgmt_menu, pattern=r"^vnd_cat_mgmt$"),
                CallbackQueryHandler(vnd_toggle_stock, pattern=r"^vnd_togp_"),
                CallbackQueryHandler(vnd_delete_product, pattern=r"^vnd_delp_"),
                CallbackQueryHandler(vnd_editp_start, pattern=r"^vnd_editp_"),
                CallbackQueryHandler(vnd_addp_start, pattern=r"^vnd_addp_start$"),
                CallbackQueryHandler(vnd_edit_delivery_start, pattern=r"^vnd_edit_delivery$"),
                CallbackQueryHandler(vnd_toggle_active, pattern=r"^vnd_toggle_active$"),
            ],
            EDIT_DELIVERY_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vnd_edit_delivery_save),
            ],
            ADD_PROD_CAT: [
                CallbackQueryHandler(vnd_addcat_start, pattern=r"^vnd_ac_start$"),
                CallbackQueryHandler(vnd_addp_name_ask, pattern=r"^vnd_ap_cat_"),
                CallbackQueryHandler(vnd_products_menu, pattern=r"^vnd_products$"),
            ],
            ADD_PROD_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vnd_addp_desc_ask),
            ],
            ADD_PROD_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vnd_addp_price_ask),
            ],
            ADD_PROD_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vnd_addp_methods_ask),
            ],
            ADD_PROD_METHODS: [
                CallbackQueryHandler(vnd_addp_method_toggle, pattern=r"^vnd_ap_m_"),
                CallbackQueryHandler(vnd_addp_save, pattern=r"^vnd_ap_save$"),
                CallbackQueryHandler(vnd_products_menu, pattern=r"^vnd_products$"),
            ],
            ADD_CAT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vnd_addcat_save),
            ],
            VND_EDITP_MENU: [
                CallbackQueryHandler(evp_name_ask, pattern=r"^evp_name$"),
                CallbackQueryHandler(evp_desc_ask, pattern=r"^evp_desc$"),
                CallbackQueryHandler(evp_price_ask, pattern=r"^evp_price$"),
                CallbackQueryHandler(evp_methods_menu, pattern=r"^evp_methods$"),
                CallbackQueryHandler(vnd_products_menu, pattern=r"^vnd_products$"),
            ],
            VND_EDITP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, evp_name_save)],
            VND_EDITP_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, evp_desc_save)],
            VND_EDITP_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, evp_price_save)],
            VND_EDITP_METHODS: [
                CallbackQueryHandler(evp_methods_toggle, pattern=r"^evp_togm_"),
                CallbackQueryHandler(vnd_products_menu, pattern=r"^vnd_products$"),
            ],
            VND_CAT_MGMT: [
                CallbackQueryHandler(vnd_addcat_start, pattern=r"^vnd_ac_start$"),
                CallbackQueryHandler(vnd_rename_cat_pick, pattern=r"^vnd_ac_rename$"),
                CallbackQueryHandler(vendor_command, pattern=r"^vendor_panel_redirect$"),
            ],
            VND_RENAME_CAT_PICK: [
                CallbackQueryHandler(vnd_rename_cat_ask, pattern=r"^vrc_p_"),
                CallbackQueryHandler(vnd_cat_mgmt_menu, pattern=r"^vnd_cat_mgmt$"),
            ],
            VND_RENAME_CAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, vnd_rename_cat_save)],
        },
        fallbacks=[
            CommandHandler("vendor", vendor_command),
            CallbackQueryHandler(vendor_command, pattern=r"^vendor_panel_redirect$"),
        ],
        per_message=False,
    )
