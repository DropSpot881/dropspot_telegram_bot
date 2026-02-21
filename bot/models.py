"""CRUD operations for all database models."""
from bot.database import get_db
from datetime import datetime, timedelta, timezone


# ── Categories ──────────────────────────────────────────────

async def get_categories(filter_methods: list[str] | None = None):
    db = await get_db()
    try:
        sql = """SELECT DISTINCT c.* 
               FROM categories c
               JOIN products p ON p.category_id = c.id
               JOIN vendors v ON p.vendor_id = v.id
               WHERE p.in_stock = 1 AND v.is_active = 1 AND v.active_until > ?"""
        
        params = [datetime.now(timezone.utc).isoformat()]
        
        if filter_methods:
            p_clauses = [f"p.allowed_delivery_methods LIKE ?" for _ in filter_methods]
            sql += " AND (" + " OR ".join(p_clauses) + ")"
            for m in filter_methods:
                params.append(f"%{m}%")
            
        sql += " ORDER BY c.name"
        
        cursor = await db.execute(sql, params)
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_all_categories():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM categories ORDER BY name")
        return await cursor.fetchall()
    finally:
        await db.close()


async def add_category(name: str):
    db = await get_db()
    try:
        await db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        await db.commit()
    finally:
        await db.close()


async def delete_category(category_id: int):
    db = await get_db()
    try:
        # 1. Get all products in this category
        cursor = await db.execute("SELECT id FROM products WHERE category_id = ?", (category_id,))
        products = await cursor.fetchall()
        
        # 2. Delete each product properly (handling their own dependencies)
        for p in products:
            await delete_product(p["id"])
            
        # 3. Finally delete the category
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()
    finally:
        await db.close()


async def update_category(category_id: int, name: str):
    db = await get_db()
    try:
        await db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
        await db.commit()
    finally:
        await db.close()


# ── Vendors ────────────────────────────────────────────────

async def add_vendor(user_id: int, username: str, display_name: str):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO vendors (user_id, username, display_name) VALUES (?, ?, ?)",
            (user_id, username, display_name),
        )
        await db.commit()
    finally:
        await db.close()


async def remove_vendor(vendor_id: int):
    db = await get_db()
    try:
        await db.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
        await db.commit()
    finally:
        await db.close()


async def get_vendor_by_user(user_id: int):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM vendors WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()
    finally:
        await db.close()


async def get_all_vendors():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM vendors ORDER BY display_name")
        return await cursor.fetchall()
    finally:
        await db.close()


async def set_vendor_active(user_id: int, active: bool, hours: int = 24):
    db = await get_db()
    try:
        until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat() if active else None
        await db.execute(
            "UPDATE vendors SET is_active = ?, active_until = ? WHERE user_id = ?",
            (1 if active else 0, until, user_id),
        )
        await db.commit()
    finally:
        await db.close()


async def update_vendor_info(user_id: int, delivery_info: str | None = None, allowed_delivery_methods: str | None = None):
    db = await get_db()
    try:
        if delivery_info is not None:
            await db.execute(
                "UPDATE vendors SET delivery_info = ? WHERE user_id = ?",
                (delivery_info, user_id),
            )
        if allowed_delivery_methods is not None:
            await db.execute(
                "UPDATE vendors SET allowed_delivery_methods = ? WHERE user_id = ?",
                (allowed_delivery_methods, user_id),
            )
        await db.commit()
    finally:
        await db.close()


async def get_active_vendors_count():
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM vendors WHERE is_active = 1 AND active_until > ?",
            (datetime.now(timezone.utc).isoformat(),)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
    finally:
        await db.close()


# ── Users & Notifications ──────────────────────────────────

async def upsert_user(user_id: int, username: str):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username = ?",
            (user_id, username, username),
        )
        await db.commit()
    finally:
        await db.close()


async def get_user(user_id: int):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()
    finally:
        await db.close()


async def toggle_notifications(user_id: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET notifications_enabled = CASE WHEN notifications_enabled = 1 THEN 0 ELSE 1 END WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def get_users_for_notifications():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT user_id FROM users WHERE notifications_enabled = 1")
        return [row["user_id"] for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_vendor_product_count(vendor_id: int):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) FROM products WHERE vendor_id = ?", (vendor_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0
    finally:
        await db.close()


# ── Products ────────────────────────────────────────────────

async def get_products_by_category(category_id: int, filter_methods: list[str] | None = None):
    db = await get_db()
    try:
        # Only show products from active vendors
        sql = """SELECT p.*, v.display_name as vendor_name 
               FROM products p 
               JOIN vendors v ON p.vendor_id = v.id 
               WHERE p.category_id = ? AND p.in_stock = 1 
               AND v.is_active = 1 AND v.active_until > ?"""
        
        params = [category_id, datetime.now(timezone.utc).isoformat()]
        
        if filter_methods:
            p_clauses = [f"p.allowed_delivery_methods LIKE ?" for _ in filter_methods]
            sql += " AND (" + " OR ".join(p_clauses) + ")"
            for m in filter_methods:
                params.append(f"%{m}%")
            
        sql += " ORDER BY p.name"
        
        cursor = await db.execute(sql, params)
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_all_products():
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT p.*, c.name as category_name, v.display_name as vendor_name 
               FROM products p 
               JOIN categories c ON p.category_id = c.id 
               LEFT JOIN vendors v ON p.vendor_id = v.id
               ORDER BY c.name, p.name"""
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def add_product(category_id: int, name: str, description: str, price: float = 0, vendor_id: int | None = None, allowed_methods: str = "dead_drop,pickup,post,today"):
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO products (category_id, name, description, price, vendor_id, allowed_delivery_methods) VALUES (?, ?, ?, ?, ?, ?)",
            (category_id, name, description, price, vendor_id, allowed_methods),
        )
        new_id = cursor.lastrowid
        await db.commit()
        return new_id
    finally:
        await db.close()


async def get_vendor_products(vendor_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM products WHERE vendor_id = ? ORDER BY name", (vendor_id,)
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def update_product(product_id: int, **kwargs):
    db = await get_db()
    try:
        if not kwargs: return
        fields = []
        params = []
        for k, v in kwargs.items():
            fields.append(f"{k} = ?")
            params.append(v)
        params.append(product_id)
        await db.execute(
            f"UPDATE products SET {', '.join(fields)} WHERE id = ?", params
        )
        await db.commit()
    finally:
        await db.close()


async def get_product(product_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT p.*, v.display_name as vendor_name 
               FROM products p 
               LEFT JOIN vendors v ON p.vendor_id = v.id 
               WHERE p.id = ?""", 
            (product_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def delete_product(product_id: int):
    db = await get_db()
    try:
        # Manual cleanup for existing databases without proper ON DELETE CASCADE
        await db.execute("DELETE FROM cart_items WHERE product_id = ?", (product_id,))
        await db.execute("UPDATE order_items SET product_id = NULL WHERE product_id = ?", (product_id,))
        await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()
    finally:
        await db.close()


async def toggle_product_stock(product_id: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE products SET in_stock = CASE WHEN in_stock = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (product_id,),
        )
        await db.commit()
    finally:
        await db.close()


# ── Dead Drop Locations ─────────────────────────────────────

async def get_available_locations():
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM dead_drop_locations WHERE is_available = 1"
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_all_locations():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM dead_drop_locations ORDER BY name")
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_location(location_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM dead_drop_locations WHERE id = ?", (location_id,)
        )
        return await cursor.fetchone()
    finally:
        await db.close()


async def add_location(name: str, address: str, description: str = "", maps_url: str = ""):
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO dead_drop_locations (name, address, description, maps_url) VALUES (?, ?, ?, ?)",
            (name, address, description, maps_url),
        )
        location_id = cursor.lastrowid
        await db.commit()
        return location_id
    finally:
        await db.close()


async def delete_location(location_id: int):
    db = await get_db()
    try:
        await db.execute("DELETE FROM dead_drop_locations WHERE id = ?", (location_id,))
        await db.commit()
    finally:
        await db.close()


async def set_location_availability(location_id: int, available: bool):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE dead_drop_locations SET is_available = ? WHERE id = ?",
            (1 if available else 0, location_id),
        )
        await db.commit()
    finally:
        await db.close()


# ── Cart ────────────────────────────────────────────────────

async def get_cart(user_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT ci.*, p.name as product_name, pv.name as variant_name, pv.price, p.in_stock FROM cart_items ci "
            "JOIN products p ON ci.product_id = p.id "
            "JOIN product_variants pv ON ci.variant_id = pv.id "
            "WHERE ci.user_id = ?",
            (user_id,),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def add_to_cart(user_id: int, product_id: int, variant_id: int, quantity: int = 1):
    db = await get_db()
    try:
        existing = await db.execute(
            "SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ? AND variant_id = ?",
            (user_id, product_id, variant_id),
        )
        row = await existing.fetchone()
        if row:
            await db.execute(
                "UPDATE cart_items SET quantity = quantity + ? WHERE user_id = ? AND product_id = ? AND variant_id = ?",
                (quantity, user_id, product_id, variant_id),
            )
        else:
            await db.execute(
                "INSERT INTO cart_items (user_id, product_id, variant_id, quantity) VALUES (?, ?, ?, ?)",
                (user_id, product_id, variant_id, quantity),
            )
        await db.commit()
    finally:
        await db.close()


async def remove_from_cart(user_id: int, product_id: int, variant_id: int):
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM cart_items WHERE user_id = ? AND product_id = ? AND variant_id = ?",
            (user_id, product_id, variant_id),
        )
        await db.commit()
    finally:
        await db.close()


async def clear_cart(user_id: int):
    db = await get_db()
    try:
        await db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await db.commit()
    finally:
        await db.close()


# ── Orders ──────────────────────────────────────────────────

async def create_order(
    user_id: int,
    username: str,
    delivery_method: str,
    payment_method: str,
    address: str,
    total: float,
    items: list,
):
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO orders (user_id, username, delivery_method, payment_method, address, total) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, delivery_method, payment_method, address, total),
        )
        order_id = cursor.lastrowid
        for item in items:
            await db.execute(
                "INSERT INTO order_items (order_id, product_id, product_name, quantity, price) "
                "VALUES (?, ?, ?, ?, ?)",
                (order_id, item["product_id"], item["name"], item["quantity"], item["price"]),
            )
        await db.commit()
        return order_id
    finally:
        await db.close()


async def get_user_orders(user_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_order(order_id: int):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_order_items(order_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_pending_orders():
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM orders WHERE status IN ('pending_payment', 'paid') ORDER BY created_at ASC"
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_all_orders():
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT 50"
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def update_order_status(order_id: int, status: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE orders SET status = ? WHERE id = ?", (status, order_id)
        )
        await db.commit()
    finally:
        await db.close()


async def update_order_address(order_id: int, address: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE orders SET address = ? WHERE id = ?", (address, order_id)
        )
        await db.commit()
    finally:
        await db.close()


async def assign_dead_drop(order_id: int, location_id: int, expiry_hours: int):
    db = await get_db()
    try:
        expires = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        await db.execute(
            "UPDATE orders SET location_id = ?, pickup_expires_at = ?, status = 'confirmed' WHERE id = ?",
            (location_id, expires.isoformat(), order_id),
        )
        await db.execute(
            "UPDATE dead_drop_locations SET is_available = 0 WHERE id = ?",
            (location_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def mark_order_paid(order_id: int):
    await update_order_status(order_id, "paid")


async def confirm_order_shipped(order_id: int):
    await update_order_status(order_id, "shipped")


async def complete_order(order_id: int):
    db = await get_db()
    try:
        order = await get_order(order_id)
        if order and order.get("location_id"):
            await db.execute(
                "UPDATE dead_drop_locations SET is_available = 1 WHERE id = ?",
                (order["location_id"],),
            )
        await db.execute(
            "UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,)
        )
        await db.commit()
    finally:
        await db.close()


async def cancel_order(order_id: int):
    db = await get_db()
    try:
        order = await get_order(order_id)
        if order and order.get("location_id"):
            await db.execute(
                "UPDATE dead_drop_locations SET is_available = 1 WHERE id = ?",
                (order["location_id"],),
            )
        await db.execute(
            "UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,)
        )
        await db.commit()
    finally:
        await db.close()


# ── Chat ───────────────────────────────────────────────────

async def add_order_message(order_id: int, sender_id: int, text: str):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO order_chats (order_id, sender_id, text) VALUES (?, ?, ?)",
            (order_id, sender_id, text),
        )
        await db.commit()
    finally:
        await db.close()


async def get_order_messages(order_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM order_chats WHERE order_id = ? ORDER BY created_at ASC",
            (order_id,),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


# ── Reviews ─────────────────────────────────────────────

async def add_review(order_id: int, user_id: int, product_id: int | None, rating: int, comment: str):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO reviews (order_id, user_id, product_id, rating, comment) VALUES (?, ?, ?, ?, ?)",
            (order_id, user_id, product_id, rating, comment),
        )
        await db.commit()
    finally:
        await db.close()


async def get_product_reviews(product_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM reviews WHERE product_id = ? ORDER BY created_at DESC",
            (product_id,),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


# ── Product Variants ────────────────────────────────────

async def add_variant(product_id: int, name: str, price: float):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO product_variants (product_id, name, price) VALUES (?, ?, ?)",
            (product_id, name, price),
        )
        await db.commit()
    finally:
        await db.close()


async def get_product_variants(product_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM product_variants WHERE product_id = ? ORDER BY price ASC",
            (product_id,),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_variant(variant_id: int):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM product_variants WHERE id = ?", (variant_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def delete_variants(product_id: int):
    db = await get_db()
    try:
        await db.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
        await db.commit()
    finally:
        await db.close()
