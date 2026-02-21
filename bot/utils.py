"""Shared utilities: keyboards, formatters, admin check, visual elements."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.config import ADMIN_IDS, SHOP_NAME


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def format_price(price: float) -> str:
    return f"{price:,.0f} kr" if price == int(price) else f"{price:,.2f} kr"


# ── Visual elements (mobile-friendly) ─────────────────────

SEP = "• • • • • • • • • • • • •"
DOT = "▪️"

def hdr(emoji: str, title: str) -> str:
    """Mobile-friendly header."""
    return f"{emoji} *{title}*\n{SEP}"


# ── Status / delivery / payment labels ─────────────────────

STATUS_EMOJI = {
    "pending_payment": "🟡",
    "paid": "🔵",
    "confirmed": "🟢",
    "shipped": "🚀",
    "completed": "✅",
    "cancelled": "🔴",
}

STATUS_LABEL = {
    "pending_payment": "Awaiting Payment",
    "paid": "Payment Received",
    "confirmed": "Confirmed",
    "shipped": "On The Way",
    "completed": "Completed",
    "cancelled": "Cancelled",
}

DELIVERY_EMOJI = {
    "dead_drop": "📍",
    "post": "📦",
    "today": "🚚",
    "pickup": "🤝",
}

DELIVERY_LABEL = {
    "dead_drop": "Deaddrop",
    "post": "Post",
    "today": "Delivery",
    "pickup": "Pick-up",
}

PAYMENT_LABEL = {
    "crypto": "₿ Crypto",
    "cash": "💵 Cash",
}


def onboarding_keyboard(notif_enabled: bool = True):
    notif_label = "🔔 Alerts: ON" if notif_enabled else "🔕 Alerts: OFF"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📬 Order to Post", callback_data="on_post")],
        [InlineKeyboardButton("🤝 Face 2 Face", callback_data="on_f2f")],
        [
            InlineKeyboardButton("🛍 Cart", callback_data="cart"),
            InlineKeyboardButton("📦 Orders", callback_data="my_orders"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="help"),
            InlineKeyboardButton(notif_label, callback_data="toggle_notifs"),
        ],
    ])


def main_menu_keyboard(notif_enabled: bool = True):
    notif_label = "🔔 Alerts: ON" if notif_enabled else "🔕 Alerts: OFF"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛒 Shop", callback_data="shop"),
            InlineKeyboardButton("🛍 Cart", callback_data="cart"),
        ],
        [
            InlineKeyboardButton("📦 Orders", callback_data="my_orders"),
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ],
        [InlineKeyboardButton(notif_label, callback_data="toggle_notifs")],
    ])


def vendor_dashboard_keyboard(is_active: bool):
    status_btn = "🔴 Go Offline" if is_active else "🟢 Go Online"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(status_btn, callback_data="toggle_notifs")], # Reusing toggle logic if possible or separate
        [
            InlineKeyboardButton("🏪 Shop", callback_data="shop"),
            InlineKeyboardButton("🛍 Cart", callback_data="cart"),
        ],
        [
            InlineKeyboardButton("📦 Orders", callback_data="my_orders"),
            InlineKeyboardButton("⚙️ Vendor Panel", callback_data="vendor_panel_redirect"),
        ],
        [InlineKeyboardButton("💬 Messages (0)", callback_data="vendor_messages")],
    ])


def back_btn(label="↩ Menu", data="main_menu"):
    return InlineKeyboardButton(label, callback_data=data)
