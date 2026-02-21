"""Main entry point — initialize bot, register handlers, run polling."""
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from bot.config import BOT_TOKEN
from bot.database import init_db

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Render.com Port Binding Workaround ─────────────────────
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return  # Silence logs for health checks

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Health check server starting on port {port}...")
    server.serve_forever()


async def post_init(application):
    """Run after bot initialization."""
    await init_db()
    logger.info("Database initialized.")


def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not set! Copy .env.example to .env and fill in your token.")
        return

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Start health check server in a background thread for Render
    threading.Thread(target=run_health_check_server, daemon=True).start()

    # ── Import handlers ────────────────────────────────────
    from bot.handlers.start import (
        start_command, main_menu_callback, help_callback, 
        toggle_notifications_callback, available_cities_callback
    )
    from bot.handlers.shop import (
        shop_callback, category_callback, product_callback, add_to_cart_callback,
        quantity_change_callback,
    )
    from bot.handlers.cart import (
        cart_callback, remove_from_cart_callback, clear_cart_callback,
        get_checkout_conversation_handler, i_paid_callback,
    )
    from bot.handlers.orders import (
        my_orders_callback, view_order_callback, 
        im_here_callback, vendor_on_way_callback, buyer_cancel_order,
    )
    from bot.handlers.admin import get_admin_conversation_handler
    from bot.handlers.vendor import get_vendor_conversation_handler, active_command, vendor_command
    from bot.handlers.chat import get_chat_conversation_handler
    from bot.handlers.reviews import get_review_conversation_handler

    # ── Register conversation handlers (must be first) ─────
    app.add_handler(get_checkout_conversation_handler())
    app.add_handler(get_admin_conversation_handler())
    app.add_handler(get_vendor_conversation_handler())
    app.add_handler(get_chat_conversation_handler())
    app.add_handler(get_review_conversation_handler())

    # ── Commands ───────────────────────────────────────────
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("active", active_command))

    # ── Callback queries ───────────────────────────────────
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern=r"^main_menu$"))
    app.add_handler(CallbackQueryHandler(help_callback, pattern=r"^help$"))
    app.add_handler(CallbackQueryHandler(toggle_notifications_callback, pattern=r"^toggle_notifs$"))
    app.add_handler(CallbackQueryHandler(shop_callback, pattern=r"^on_post$"))
    app.add_handler(CallbackQueryHandler(available_cities_callback, pattern=r"^on_f2f$"))
    app.add_handler(CallbackQueryHandler(shop_callback, pattern=r"^shop$"))
    app.add_handler(CallbackQueryHandler(category_callback, pattern=r"^cat_\d+$"))
    app.add_handler(CallbackQueryHandler(product_callback, pattern=r"^prod_\d+$"))
    app.add_handler(CallbackQueryHandler(add_to_cart_callback, pattern=r"^addcart_\d+$"))
    app.add_handler(CallbackQueryHandler(cart_callback, pattern=r"^cart$"))
    app.add_handler(CallbackQueryHandler(remove_from_cart_callback, pattern=r"^rmcart_\d+$"))
    app.add_handler(CallbackQueryHandler(clear_cart_callback, pattern=r"^clear_cart$"))
    app.add_handler(CallbackQueryHandler(my_orders_callback, pattern=r"^my_orders$"))
    app.add_handler(CallbackQueryHandler(view_order_callback, pattern=r"^vieworder_\d+$"))
    app.add_handler(CallbackQueryHandler(quantity_change_callback, pattern=r"^qty_(inc|dec)_\d+$"))
    app.add_handler(CallbackQueryHandler(im_here_callback, pattern=r"^imhere_\d+$"))
    app.add_handler(CallbackQueryHandler(vendor_on_way_callback, pattern=r"^vonway_\d+$"))
    app.add_handler(CallbackQueryHandler(buyer_cancel_order, pattern=r"^buyercancel_\d+$"))
    app.add_handler(CallbackQueryHandler(i_paid_callback, pattern=r"^ipaid_\d+$"))

    # ── Admin callbacks (outside conversation) ─────────────
    # Handled by get_admin_conversation_handler() entry points

    logger.info("🤖 Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
