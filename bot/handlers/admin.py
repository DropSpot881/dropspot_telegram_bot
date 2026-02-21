"""Admin handler — manage products, categories, locations, orders."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler,
)
from bot import models
from bot.utils import (
    is_admin, format_price, STATUS_EMOJI, STATUS_LABEL,
    DELIVERY_LABEL, DELIVERY_EMOJI, PAYMENT_LABEL,
    hdr, SEP, back_btn,
)
from bot.config import PICKUP_EXPIRY_HOURS
import random

(
    ADMIN_MENU,
    ADD_CATEGORY_NAME,
    ADD_PRODUCT_CATEGORY, ADD_PRODUCT_NAME, ADD_PRODUCT_DESC, ADD_PRODUCT_PRICE, ADD_PRODUCT_VENDOR,
    ADD_LOCATION_NAME, ADD_LOCATION_ADDRESS, ADD_LOCATION_MAPS, ADD_LOCATION_DESC,
    ADD_FRESH_LOC_NAME, ADD_FRESH_LOC_ADDR, ADD_FRESH_LOC_MAPS, ADD_FRESH_LOC_DESC,
    ADD_VENDOR_USER_ID, ADD_VENDOR_NAME,
    WAITING_PICKUP_DETAILS,
) = range(18)


def admin_check(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not is_admin(user_id):
            if update.callback_query:
                await update.callback_query.answer("⛔ Admin only.", show_alert=True)
            elif update.message:
                await update.message.reply_text("⛔ Not authorized.")
            return ConversationHandler.END
        return await func(update, context)
    return wrapper


# ── Admin Menu ─────────────────────────────────────────────

@admin_check
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"🔧 *Admin Panel*\n{SEP}\n\n"
        "Select a section 👇"
    )
    buttons = [
        [
            InlineKeyboardButton("📂 Categories", callback_data="adm_categories"),
            InlineKeyboardButton("📦 Products", callback_data="adm_products"),
        ],
        [
            InlineKeyboardButton("📍 Locations", callback_data="adm_locations"),
            InlineKeyboardButton("🤝 Vendors", callback_data="adm_vendors"),
        ],
        [
            InlineKeyboardButton("🔔 Pending", callback_data="adm_pending"),
            InlineKeyboardButton("📜 All Orders", callback_data="adm_all_orders"),
        ],
    ]
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_MENU


# ── Categories ─────────────────────────────────────────────

@admin_check
async def adm_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cats = await models.get_categories()

    lines = [f"{hdr('📂', 'Categories')}\n"]
    buttons = []
    for c in cats:
        prods = await models.get_products_by_category(c['id'])
        lines.append(f"• *{c['name']}* ({len(prods)} items)")
        buttons.append([InlineKeyboardButton(f"🗑 {c['name']}", callback_data=f"adm_delcat_{c['id']}")])
    if not cats:
        lines.append("_None yet._")

    buttons.append([InlineKeyboardButton("➕ Add", callback_data="adm_addcat")])
    buttons.append([InlineKeyboardButton("↩ Admin", callback_data="adm_menu")])
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_MENU


@admin_check
async def adm_addcat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"{hdr('📂', 'New Category')}\n\nEnter name ✍️", parse_mode="Markdown")
    return ADD_CATEGORY_NAME


@admin_check
async def adm_addcat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("❌ Can't be empty. Try again:")
        return ADD_CATEGORY_NAME
    try:
        await models.add_category(name)
        await update.message.reply_text(f"✅ *{name}* created!", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("❌ Error or already exists.")
    await update.message.reply_text(
        "Continue 👇",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ Admin", callback_data="adm_menu")]]),
    )
    return ADMIN_MENU


@admin_check
async def adm_delcat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🗑 Deleted!", show_alert=True)
    cat_id = int(query.data.split("_")[2])
    await models.delete_category(cat_id)
    await adm_categories(update, context)
    return ADMIN_MENU


# ── Products ───────────────────────────────────────────────

@admin_check
async def adm_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    products = await models.get_all_products()

    lines = [f"{hdr('📦', 'Products')}\n"]
    buttons = []
    for p in products:
        s = "🟢" if p["in_stock"] else "🔴"
        lines.append(f"{s} *{p['name']}* — {format_price(p['price'])}")
        buttons.append([
            InlineKeyboardButton(f"🔄 {p['name']}", callback_data=f"adm_togprod_{p['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"adm_delprod_{p['id']}"),
        ])
    if not products:
        lines.append("_None yet._")

    buttons.append([InlineKeyboardButton("➕ Add", callback_data="adm_addprod")])
    buttons.append([InlineKeyboardButton("↩ Admin", callback_data="adm_menu")])
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_MENU


@admin_check
async def adm_addprod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cats = await models.get_categories()
    if not cats:
        await query.edit_message_text(
            "❌ Create a category first!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 Categories", callback_data="adm_categories")],
                [InlineKeyboardButton("↩ Admin", callback_data="adm_menu")],
            ]),
        )
        return ADMIN_MENU

    buttons = [[InlineKeyboardButton(f"📂 {c['name']}", callback_data=f"adm_prodcat_{c['id']}")] for c in cats]
    buttons.append([InlineKeyboardButton("✖ Cancel", callback_data="adm_menu")])
    await query.edit_message_text(
        f"{hdr('📦', 'New Product')}\n\n*Step 1/4* — Category 👇",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return ADD_PRODUCT_CATEGORY


@admin_check
async def adm_prodcat_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["new_product_cat"] = int(query.data.split("_")[2])
    await query.edit_message_text(
        f"{hdr('📦', 'New Product')}\n\n*Step 2/4* — Name ✍️", parse_mode="Markdown")
    return ADD_PRODUCT_NAME


@admin_check
async def adm_prodname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product_name"] = update.message.text.strip()
    await update.message.reply_text("*Step 3/4* — Description ✍️", parse_mode="Markdown")
    return ADD_PRODUCT_DESC


@admin_check
async def adm_proddesc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product_desc"] = update.message.text.strip()
    await update.message.reply_text("*Step 4/4* — Price (e.g. `199`) ✍️", parse_mode="Markdown")
    return ADD_PRODUCT_PRICE


@admin_check
async def adm_prodprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Try again:")
        return ADD_PRODUCT_PRICE
    context.user_data["new_product_price"] = price
    
    vendors = await models.get_all_vendors()
    buttons = [[InlineKeyboardButton(f"👤 {v['display_name']}", callback_data=f"adm_pvd_{v['id']}")] for v in vendors]
    buttons.append([InlineKeyboardButton("❌ No Vendor / Admin", callback_data="adm_pvd_none")])
    buttons.append([InlineKeyboardButton("✖ Cancel", callback_data="adm_menu")])
    
    await update.message.reply_text(
        f"{hdr('📦', 'New Product')}\n\n*Step 5/5* — Assign to Vendor 👇",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return ADD_PRODUCT_VENDOR


@admin_check
async def adm_prodvendor_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.replace("adm_pvd_", "")
    vendor_id = int(data) if data != "none" else None
    
    cat_id = context.user_data["new_product_cat"]
    name = context.user_data["new_product_name"]
    desc = context.user_data["new_product_desc"]
    price = context.user_data["new_product_price"]
    
    await models.add_product(cat_id, name, desc, price, vendor_id)
    await query.edit_message_text(
        f"✅ *{name}* — {format_price(price)} added!", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 Products", callback_data="adm_products")],
            [InlineKeyboardButton("↩ Admin", callback_data="adm_menu")],
        ]),
    )
    return ADMIN_MENU


@admin_check
async def adm_togprod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await models.toggle_product_stock(int(query.data.split("_")[2]))
    await query.answer("🔄 Toggled!", show_alert=True)
    await adm_products(update, context)
    return ADMIN_MENU


@admin_check
async def adm_delprod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await models.delete_product(int(query.data.split("_")[2]))
    await query.answer("🗑 Deleted!", show_alert=True)
    await adm_products(update, context)
    return ADMIN_MENU


# ── Locations ──────────────────────────────────────────────

@admin_check
async def adm_locations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    locs = await models.get_all_locations()

    lines = [f"{hdr('📍', 'Locations')}\n"]
    buttons = []
    for l in locs:
        status = "🟢 Available" if l["is_available"] else "🔴 Occupied"
        lines.append(f"📍 *{l['name']}*\n   {status}\n   🗺 {l['address']}")
        buttons.append([
            InlineKeyboardButton(f"🔄 Toggle Status", callback_data=f"adm_togloc_{l['id']}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"adm_delloc_{l['id']}"),
        ])
    if not locs:
        lines.append("_None yet._")

    buttons.append([InlineKeyboardButton("➕ Add New Location", callback_data="adm_addloc")])
    buttons.append([InlineKeyboardButton("↩ Admin Menu", callback_data="adm_menu")])
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_MENU


@admin_check
async def adm_addloc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"{hdr('📍', 'New Location')}\n\n*Step 1/3* — Name ✍️", parse_mode="Markdown")
    return ADD_LOCATION_NAME


@admin_check
async def adm_locname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_loc_name"] = update.message.text.strip()
    await update.message.reply_text("*Step 2/3* — Address ✍️", parse_mode="Markdown")
    return ADD_LOCATION_ADDRESS


@admin_check
async def adm_locaddr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_loc_addr"] = update.message.text.strip()
    await update.message.reply_text("*Step 3/4* — Maps Link (Google/Apple) ✍️", parse_mode="Markdown")
    return ADD_LOCATION_MAPS


@admin_check
async def adm_locmaps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_loc_maps"] = update.message.text.strip()
    await update.message.reply_text("*Step 4/4* — Description (or `skip`) ✍️", parse_mode="Markdown")
    return ADD_LOCATION_DESC


@admin_check
async def adm_locdesc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if desc.lower() == "skip":
        desc = ""
    name = context.user_data["new_loc_name"]
    await models.add_location(
        name, 
        context.user_data["new_loc_addr"], 
        desc,
        context.user_data["new_loc_maps"]
    )
    await update.message.reply_text(
        f"✅ *{name}* added!", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📍 Locations", callback_data="adm_locations")],
            [InlineKeyboardButton("↩ Admin", callback_data="adm_menu")],
        ]),
    )
    return ADMIN_MENU


@admin_check
async def adm_togloc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    loc_id = int(query.data.split("_")[2])
    loc = await models.get_location(loc_id)
    if loc:
        await models.set_location_availability(loc_id, not bool(loc["is_available"]))
    await query.answer("🔄 Toggled!", show_alert=True)
    await adm_locations(update, context)
    return ADMIN_MENU


@admin_check
async def adm_delloc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await models.delete_location(int(query.data.split("_")[2]))
    await query.answer("🗑 Deleted!", show_alert=True)
    await adm_locations(update, context)
    return ADMIN_MENU


# ── Vendors Management ─────────────────────────────────────

@admin_check
async def adm_vendors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vendors = await models.get_all_vendors()

    lines = [f"{hdr('🤝', 'Vendors')}\n"]
    buttons = []
    for v in vendors:
        status = "🟢 Active" if v["is_active"] else "🔴 Inactive"
        lines.append(f"👤 *{v['display_name']}* (@{v['username']})\n   {status}")
        buttons.append([InlineKeyboardButton(f"🗑 {v['display_name']}", callback_data=f"adm_delvnd_{v['id']}")])
    
    if not vendors:
        lines.append("_No vendors registered._")

    buttons.append([InlineKeyboardButton("➕ Add New Vendor", callback_data="adm_addvnd")])
    buttons.append([InlineKeyboardButton("↩ Admin Menu", callback_data="adm_menu")])
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_MENU


@admin_check
async def adm_addvnd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        f"{hdr('🤝', 'New Vendor')}\n\n*Step 1/2* — Enter Telegram User ID ✍️\n\n_User can get it from @userinfobot_", parse_mode="Markdown")
    return ADD_VENDOR_USER_ID


@admin_check
async def adm_addvnd_userid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text.strip())
        context.user_data["new_vnd_userid"] = user_id
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Must be a number:")
        return ADD_VENDOR_USER_ID
    
    await update.message.reply_text("*Step 2/2* — Enter Display Name ✍️", parse_mode="Markdown")
    return ADD_VENDOR_NAME


@admin_check
async def adm_addvnd_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    display_name = update.message.text.strip()
    user_id = context.user_data["new_vnd_userid"]
    
    # Try to get username if possible, otherwise empty
    await models.add_vendor(user_id, "", display_name)
    await update.message.reply_text(
        f"✅ Vendor *{display_name}* registered!", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ Admin", callback_data="adm_menu")]]),
    )
    return ADMIN_MENU


@admin_check
async def adm_delvnd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    vnd_id = int(query.data.split("_")[2])
    await models.remove_vendor(vnd_id)
    await query.answer("🗑 Deleted!", show_alert=True)
    await adm_vendors(update, context)
    return ADMIN_MENU


# ── Orders ─────────────────────────────────────────────────

@admin_check
async def adm_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    orders = await models.get_pending_orders()

    if not orders:
        await query.edit_message_text(
            f"{hdr('🔔', 'Pending')}\n\n✅ All clear!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ Admin", callback_data="adm_menu")]]),
        )
        return ADMIN_MENU

    lines = [f"{hdr('🔔', 'Pending Orders')}\n"]
    buttons = []
    for o in orders:
        e = STATUS_EMOJI.get(o["status"], "❓")
        d = DELIVERY_EMOJI.get(o["delivery_method"], "📦")
        lines.append(f"{e} *#{o['id']}* · @{o['username']} · {format_price(o['total'])}")
        buttons.append([InlineKeyboardButton(f"📋 #{o['id']}", callback_data=f"admin_order_{o['id']}")])
    buttons.append([InlineKeyboardButton("↩ Admin", callback_data="adm_menu")])
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_MENU


@admin_check
async def adm_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    orders = await models.get_all_orders()

    if not orders:
        await query.edit_message_text(
            f"{hdr('📜', 'All Orders')}\n\n_None yet._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ Admin", callback_data="adm_menu")]]),
        )
        return ADMIN_MENU

    lines = [f"{hdr('📜', 'All Orders')}\n"]
    buttons = []
    for o in orders:
        e = STATUS_EMOJI.get(o["status"], "❓")
        l = STATUS_LABEL.get(o["status"], o["status"])
        lines.append(f"{e} *#{o['id']}* · @{o['username']} · {format_price(o['total'])} · {l}")
        buttons.append([InlineKeyboardButton(f"📋 #{o['id']}", callback_data=f"admin_order_{o['id']}")])
    buttons.append([InlineKeyboardButton("↩ Admin", callback_data="adm_menu")])
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_MENU


@admin_check
async def admin_view_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[2])

    order = await models.get_order(order_id)
    if not order:
        await query.edit_message_text("❌ Not found.")
        return ADMIN_MENU

    items = await models.get_order_items(order_id)
    e = STATUS_EMOJI.get(order["status"], "❓")
    d = DELIVERY_EMOJI.get(order["delivery_method"], "📦")

    lines = [
        f"📋 *Order #{order_id}*\n{SEP}\n",
        f"👤 @{order['username']} (`{order['user_id']}`)",
        f"{e} *{STATUS_LABEL.get(order['status'], order['status'])}*",
        f"{d} {DELIVERY_LABEL.get(order['delivery_method'], '')}",
        f"💳 {PAYMENT_LABEL.get(order['payment_method'], '')}",
        f"💰 *{format_price(order['total'])}*",
    ]
    if order["address"]:
        lines.append(f"📬 _{order['address']}_")
    if order["location_id"]:
        loc = await models.get_location(order["location_id"])
        if loc:
            lines.append(f"📍 *{loc['name']}* — {loc['address']}")

    lines.append(f"\n*Items:*")
    for it in items:
        lines.append(f"• {it['product_name']} ×{it['quantity']} = *{format_price(it['price'] * it['quantity'])}*")

    buttons = []
    st = order["status"]
    if st in ("pending_payment", "paid"):
        if order["delivery_method"] == "dead_drop":
            buttons.append([InlineKeyboardButton("🎲 Assign Random Location", callback_data=f"admin_confirm_{order_id}")])
            buttons.append([InlineKeyboardButton("➕ Add Fresh Location", callback_data=f"admin_freshloc_{order_id}")])
        else:
            buttons.append([InlineKeyboardButton("✅ Confirm Order", callback_data=f"admin_confirm_{order_id}")])
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cancel_{order_id}")])
    if st == "confirmed" and order["delivery_method"] in ("post", "today"):
        buttons.append([InlineKeyboardButton("🚚 Ship", callback_data=f"admin_ship_{order_id}")])
    if st in ("confirmed", "shipped"):
        buttons.append([InlineKeyboardButton("✔️ Complete", callback_data=f"admin_complete_{order_id}")])
    buttons.append([
        InlineKeyboardButton("💬 Chat", callback_data=f"orderchat_{order_id}")
    ])
    buttons.append([InlineKeyboardButton("🔔 Pending", callback_data="adm_pending")])
    buttons.append([InlineKeyboardButton("↩ Admin", callback_data="adm_menu")])

    await query.edit_message_text(
        "\n".join(lines), 
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return ADMIN_MENU


@admin_check
async def admin_confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[2])
    order = await models.get_order(order_id)
    if not order:
        await query.edit_message_text("❌ Not found.")
        return ADMIN_MENU

    if order["delivery_method"] == "dead_drop":
        locs = await models.get_available_locations()
        if not locs:
            await query.edit_message_text(
                "❌ No locations available!\nAdd more first.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📍 Locations", callback_data="adm_locations")],
                    [InlineKeyboardButton("↩ Admin", callback_data="adm_menu")],
                ]),
            )
            return ADMIN_MENU

        chosen = random.choice(locs)
        await models.assign_dead_drop(order_id, chosen["id"], PICKUP_EXPIRY_HOURS)
        
        maps_text = f'\n🗺 <a href="{chosen["maps_url"]}">Open in Maps</a>' if chosen['maps_url'] else f"\n🗺 {chosen['address']}"
        
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=(
                    f"✅ <b>Order #{order_id} Confirmed!</b>\n{SEP}\n\n"
                    f"📍 <b>Pickup Location:</b>\n\n"
                    f"📌 <b>{chosen['name']}</b>"
                    f"{maps_text}\n"
                    + (f"ℹ️ <i>{chosen['description']}</i>\n" if chosen['description'] else "")
                    + f"\n⏰ Pick up within <b>{PICKUP_EXPIRY_HOURS}h</b>"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
        await query.edit_message_text(
            f"✅ #{order_id} confirmed!\n📍 → <b>{chosen['name']}</b>", 
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 Pending", callback_data="adm_pending")],
                [InlineKeyboardButton("↩ Admin", callback_data="adm_menu")],
            ]),
        )
    elif order["delivery_method"] == "pickup":
        context.user_data["confirming_order_id"] = order_id
        await query.edit_message_text(
            f"{hdr('🤝', 'Confirm Pick-up')}\n\n"
            f"Order *#{order_id}*\n\n"
            "Enter the meeting point / address for the buyer ✍️\n\n"
            "_This will be sent to the customer instantly._",
            parse_mode="Markdown"
        )
        return WAITING_PICKUP_DETAILS
    else:
        await models.update_order_status(order_id, "confirmed")
        d = DELIVERY_EMOJI.get(order["delivery_method"], "📦")
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=(
                    f"✅ <b>Order #{order_id} Confirmed!</b>\n{SEP}\n\n"
                    f"{d} {DELIVERY_LABEL.get(order['delivery_method'], '')}\n"
                    "📦 Being prepared for shipping!"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
        await query.edit_message_text(
            f"✅ #{order_id} confirmed!", 
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 Pending", callback_data="adm_pending")],
                [InlineKeyboardButton("↩ Admin", callback_data="adm_menu")],
            ]),
        )
    return ADMIN_MENU


@admin_check
async def admin_pickup_confirm_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = update.message.text.strip()
    order_id = context.user_data.get("confirming_order_id")
    if not order_id:
        await update.message.reply_text("❌ Session expired. Start over.")
        return ADMIN_MENU
    
    order = await models.get_order(order_id)
    await models.update_order_status(order_id, "confirmed")
    # Store pickup details in address field for later reference
    await models.update_order_address(order_id, details)
    
    try:
        buttons = [
            [InlineKeyboardButton("📍 I'm here", callback_data=f"imhere_{order_id}")],
            [InlineKeyboardButton("✖ Cancel Order", callback_data=f"buyercancel_{order_id}")],
        ]
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=(
                f"✅ <b>Order #{order_id} Confirmed!</b>\n{SEP}\n\n"
                f"🤝 <b>Method:</b> Pick-up\n"
                f"📍 <b>Meeting Point:</b>\n\n"
                f"{details}\n\n"
                "<i>Please head to the location as arranged. Click below when you arrive!</i>"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        pass
    
    await update.message.reply_text(
        f"✅ Order #{order_id} confirmed and pickup details sent!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩ Admin Menu", callback_data="adm_menu")]
        ])
    )
    context.user_data.pop("confirming_order_id", None)
    return ADMIN_MENU


@admin_check
async def admin_freshloc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start fresh location entry for an order."""
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[2])
    context.user_data["assigning_order_id"] = order_id

    await query.edit_message_text(
        f"{hdr('📍', 'Fresh Location')}\n\n"
        f"Order *#{order_id}*\n\n"
        "Enter a name for this one-time spot ✍️",
        parse_mode="Markdown",
    )
    return ADD_FRESH_LOC_NAME


@admin_check
async def admin_freshloc_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["fresh_loc_name"] = update.message.text.strip()
    await update.message.reply_text("Enter the address / directions ✍️", parse_mode="Markdown")
    return ADD_FRESH_LOC_ADDR


@admin_check
async def admin_freshloc_addr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["fresh_loc_addr"] = update.message.text.strip()
    await update.message.reply_text("Enter Maps Link (Google/Apple) ✍️", parse_mode="Markdown")
    return ADD_FRESH_LOC_MAPS


@admin_check
async def admin_freshloc_maps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["fresh_loc_maps"] = update.message.text.strip()
    await update.message.reply_text("Enter extra details (or `skip`) ✍️", parse_mode="Markdown")
    return ADD_FRESH_LOC_DESC


@admin_check
async def admin_freshloc_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if desc.lower() == "skip":
        desc = ""
    
    order_id = context.user_data["assigning_order_id"]
    name = context.user_data["fresh_loc_name"]
    addr = context.user_data["fresh_loc_addr"]
    maps_url = context.user_data["fresh_loc_maps"]
    
    # 1. Add it to DB as occupied
    loc_id = await models.add_location(name, addr, desc, maps_url)
    await models.set_location_availability(loc_id, False) # Occupied by this user
    
    # 2. Assign to order
    await models.assign_dead_drop(order_id, loc_id, PICKUP_EXPIRY_HOURS)
    
    order = await models.get_order(order_id)
    maps_text = f'\n🗺 <a href="{maps_url}">Open in Maps</a>' if maps_url else f"\n🗺 {addr}"
    
    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=(
                f"✅ <b>Order #{order_id} Confirmed!</b>\n{SEP}\n\n"
                f"📍 <b>Pickup Location:</b>\n\n"
                f"📌 <b>{name}</b>"
                f"{maps_text}\n"
                + (f"ℹ️ <i>{desc}</i>\n" if desc else "")
                + f"\n⏰ Pick up within <b>{PICKUP_EXPIRY_HOURS}h</b>"
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ Location <b>{name}</b> assigned to <b>#{order_id}</b>!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩ Admin Menu", callback_data="adm_menu")]
        ]),
    )
    context.user_data.pop("assigning_order_id", None)
    return ADMIN_MENU


@admin_check
async def admin_ship_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[2])
    await models.confirm_order_shipped(order_id)
    order = await models.get_order(order_id)
    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=f"🚀 *Order #{order_id} Shipped!*\n\nOn its way to you! 📬",
            parse_mode="Markdown",
        )
    except Exception:
        pass
    await query.edit_message_text(
        f"🚚 #{order_id} shipped!", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔔 Pending", callback_data="adm_pending")],
            [InlineKeyboardButton("↩ Admin", callback_data="adm_menu")],
        ]),
    )
    return ADMIN_MENU


@admin_check
async def admin_complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[2])
    await models.complete_order(order_id)
    order = await models.get_order(order_id)
    try:
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("⭐ Leave a Review", callback_data=f"review_{order_id}")
        ]])
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=f"🎉 *Order #{order_id} Complete!*\n\nThank you! See you again 💫",
            parse_mode="Markdown",
            reply_markup=markup
        )
    except Exception:
        pass
    await query.edit_message_text(
        f"✔️ #{order_id} completed!", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ Admin", callback_data="adm_menu")]]),
    )
    return ADMIN_MENU


@admin_check
async def admin_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[2])
    await models.cancel_order(order_id)
    order = await models.get_order(order_id)
    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=f"❌ *Order #{order_id} Cancelled*\n\nContact us if you have questions.",
            parse_mode="Markdown",
        )
    except Exception:
        pass
    await query.edit_message_text(
        f"❌ #{order_id} cancelled.", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩ Admin", callback_data="adm_menu")]]),
    )
    return ADMIN_MENU


def get_admin_conversation_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_command),
            CallbackQueryHandler(admin_command, pattern=r"^adm_menu$"),
            CallbackQueryHandler(adm_pending_orders, pattern=r"^adm_pending$"),
            CallbackQueryHandler(adm_all_orders, pattern=r"^adm_all_orders$"),
            CallbackQueryHandler(admin_view_order, pattern=r"^admin_order_\d+$"),
            CallbackQueryHandler(admin_confirm_order, pattern=r"^admin_confirm_\d+$"),
            CallbackQueryHandler(admin_freshloc_start, pattern=r"^admin_freshloc_\d+$"),
            CallbackQueryHandler(admin_cancel_order, pattern=r"^admin_cancel_\d+$"),
            CallbackQueryHandler(admin_ship_order, pattern=r"^admin_ship_\d+$"),
            CallbackQueryHandler(admin_complete_order, pattern=r"^admin_complete_\d+$"),
        ],
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(adm_categories, pattern=r"^adm_categories$"),
                CallbackQueryHandler(adm_products, pattern=r"^adm_products$"),
                CallbackQueryHandler(adm_locations, pattern=r"^adm_locations$"),
                CallbackQueryHandler(adm_vendors, pattern=r"^adm_vendors$"),
                CallbackQueryHandler(adm_pending_orders, pattern=r"^adm_pending$"),
                CallbackQueryHandler(adm_all_orders, pattern=r"^adm_all_orders$"),
                CallbackQueryHandler(adm_addcat_start, pattern=r"^adm_addcat$"),
                CallbackQueryHandler(adm_addprod_start, pattern=r"^adm_addprod$"),
                CallbackQueryHandler(adm_addloc_start, pattern=r"^adm_addloc$"),
                CallbackQueryHandler(adm_addvnd_start, pattern=r"^adm_addvnd$"),
                CallbackQueryHandler(adm_delcat, pattern=r"^adm_delcat_\d+$"),
                CallbackQueryHandler(adm_togprod, pattern=r"^adm_togprod_\d+$"),
                CallbackQueryHandler(adm_delprod, pattern=r"^adm_delprod_\d+$"),
                CallbackQueryHandler(adm_togloc, pattern=r"^adm_togloc_\d+$"),
                CallbackQueryHandler(adm_delloc, pattern=r"^adm_delloc_\d+$"),
                CallbackQueryHandler(adm_delvnd, pattern=r"^adm_delvnd_\d+$"),
                CallbackQueryHandler(admin_view_order, pattern=r"^admin_order_\d+$"),
                CallbackQueryHandler(admin_confirm_order, pattern=r"^admin_confirm_\d+$"),
                CallbackQueryHandler(admin_freshloc_start, pattern=r"^admin_freshloc_\d+$"),
                CallbackQueryHandler(admin_cancel_order, pattern=r"^admin_cancel_\d+$"),
                CallbackQueryHandler(admin_ship_order, pattern=r"^admin_ship_\d+$"),
                CallbackQueryHandler(admin_complete_order, pattern=r"^admin_complete_\d+$"),
            ],
            WAITING_PICKUP_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_pickup_confirm_save),
            ],
            ADD_CATEGORY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_addcat_name)],
            ADD_PRODUCT_CATEGORY: [
                CallbackQueryHandler(adm_prodcat_chosen, pattern=r"^adm_prodcat_\d+$"),
                CallbackQueryHandler(admin_command, pattern=r"^adm_menu$"),
            ],
            ADD_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_prodname)],
            ADD_PRODUCT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_proddesc)],
            ADD_PRODUCT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_prodprice)],
            ADD_PRODUCT_VENDOR: [
                CallbackQueryHandler(adm_prodvendor_chosen, pattern=r"^adm_pvd_"),
                CallbackQueryHandler(admin_command, pattern=r"^adm_menu$"),
            ],
            ADD_LOCATION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_locname)],
            ADD_LOCATION_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_locaddr)],
            ADD_LOCATION_MAPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_locmaps)],
            ADD_LOCATION_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_locdesc)],
            ADD_FRESH_LOC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_freshloc_name)],
            ADD_FRESH_LOC_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_freshloc_addr)],
            ADD_FRESH_LOC_MAPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_freshloc_maps)],
            ADD_FRESH_LOC_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_freshloc_desc)],
            ADD_VENDOR_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_addvnd_userid)],
            ADD_VENDOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_addvnd_name)],
        },
        fallbacks=[CallbackQueryHandler(admin_command, pattern=r"^adm_menu$")],
        per_message=False,
    )
