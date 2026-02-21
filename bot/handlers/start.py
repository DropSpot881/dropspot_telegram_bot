"""Start handler — /start command and main menu."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.config import SHOP_NAME
from bot.utils import onboarding_keyboard, vendor_dashboard_keyboard, hdr, SEP, back_btn
from bot import models


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # 1. Track user and get common data
    await models.upsert_user(user.id, user.username or user.first_name)
    user_db = await models.get_user(user.id)
    notif_enabled = bool(user_db["notifications_enabled"]) if user_db else True
    
    # 2. Check if user is a vendor
    vendor = await models.get_vendor_by_user(user.id)
    
    if vendor:
        # ── Vendor Dashboard View ──
        prod_count = await models.get_vendor_product_count(vendor["id"])
        status_text = "🟢 ONLINE" if vendor["is_active"] else "🔴 OFFLINE"
        
        text = (
            f"🏪 *Vendor Dashboard*\n{SEP}\n\n"
            f"Hey {vendor['display_name']}! 👋\n\n"
            f"📊 *Stats:*\n"
            f"📦 Listings: {prod_count}\n"
            f"📍 Status: {status_text}\n\n"
            f"You can toggle your active status or manage listings from the Vendor Panel. 🚀"
        )
        markup = vendor_dashboard_keyboard(bool(vendor["is_active"]))
    else:
        # ── Regular Customer View (Onboarding) ──
        active_count = await models.get_active_vendors_count()
        vendor_status = f"🟢 {active_count} Plugs Active" if active_count > 0 else "🔴 Shop Closed (No Active Plugs)"

        text = (
            f"🏪 *{SHOP_NAME}*\n\n"
            f"Hey {user.first_name}! 👋\n\n"
            f"{vendor_status}\n\n"
            f"Welcome to our discreet shop! 🛡\n"
            "How would you like to receive your order?\n\n"
            f"{SEP}\n"
            f"Pick an option below 👇"
        )
        markup = onboarding_keyboard(notif_enabled)
    
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def available_cities_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Fetch cities from dead_drop_locations
    db = await models.get_db()
    cursor = await db.execute("SELECT DISTINCT name FROM dead_drop_locations WHERE is_available = 1")
    rows = await cursor.fetchall()
    await db.close()
    
    cities = [r["name"] for r in rows]
    
    if not cities:
        # Fallback or placeholder cities if none in DB
        cities = ["Kristiansand", "Arendal", "Vennesla"]
    
    text = (
        f"{hdr('🏙', 'Available Cities')}\n\n"
        "We are currently active in these locations for Face 2 Face / Deaddrop delivery:\n\n"
        "Select a city to browse products in that area 👇"
    )
    
    buttons = []
    for city in cities:
        # For now, all cities just lead to the general shop
        # In a real setup, we might filter by vendor locations if we had that
        buttons.append([InlineKeyboardButton(f"📍 {city}", callback_data="shop")])
    
    buttons.append([back_btn()])
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start_command(update, context)


async def toggle_notifications_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    # Check if this is a vendor toggling their shop or a user toggling alerts
    vendor = await models.get_vendor_by_user(user_id)
    if vendor:
        # Vendor toggling shop status
        from bot.handlers.vendor import vnd_toggle_active
        await vnd_toggle_active(update, context)
        return

    # Regular user toggling notifications
    await models.toggle_notifications(user_id)
    user_db = await models.get_user(user_id)
    notif_enabled = bool(user_db["notifications_enabled"])
    
    status_text = "ENABLED ✅" if notif_enabled else "DISABLED ❌"
    await query.answer(f"Notifications {status_text}", show_alert=True)
    
    # Refresh menu
    await start_command(update, context)


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        f"{hdr('📖', 'How To Order')}\n\n"
        "*1.* 🛒 Browse & add items to cart\n\n"
        "*2.* 📍 Choose delivery:\n"
        "  • Deaddrop (secret spot)\n"
        "  • Post (shipping)\n"
        "  • Pick-up (F2F)\n"
        "  • Delivery (door)\n\n"
        "*3.* 💳 Choose payment:\n"
        "  • ₿ Crypto (BTC/ETH)\n"
        "  • 💵 Cash\n\n"
        "*4.* ✅ Confirm & pay\n\n"
        "*5.* 📦 Get delivery info!\n\n"
        f"{SEP}\n"
        "Track orders under *Orders* 📦"
    )

    # Need context-aware keyboard (cust or vendor)
    user_db = await models.get_user(query.from_user.id)
    notif_enabled = bool(user_db["notifications_enabled"]) if user_db else True
    
    vendor = await models.get_vendor_by_user(query.from_user.id)
    if vendor:
        markup = vendor_dashboard_keyboard(bool(vendor["is_active"]))
    else:
        markup = onboarding_keyboard(notif_enabled)

    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
