import aiosqlite
from bot.config import DB_PATH


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


async def init_db():
    """Create all tables on startup."""
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                username TEXT DEFAULT '',
                display_name TEXT DEFAULT '',
                is_active INTEGER DEFAULT 0,
                active_until TIMESTAMP,
                delivery_info TEXT DEFAULT '',
                allowed_delivery_methods TEXT DEFAULT 'delivery,pickup,post,deaddrop',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                vendor_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                in_stock INTEGER DEFAULT 1,
                allowed_delivery_methods TEXT DEFAULT 'dead_drop,pickup,post,today',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
                FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS dead_drop_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                description TEXT DEFAULT '',
                maps_url TEXT DEFAULT '',
                is_available INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT '',
                status TEXT DEFAULT 'pending_payment',
                delivery_method TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                address TEXT DEFAULT '',
                pickup_expires_at TIMESTAMP,
                total REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES dead_drop_locations(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                order_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER DEFAULT 5,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS product_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS cart_items (
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                variant_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, product_id, variant_id),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                username TEXT DEFAULT '',
                notifications_enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS order_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            );
        """)

        # Migrations for existing databases
        migrations = [
            "ALTER TABLE dead_drop_locations ADD COLUMN maps_url TEXT DEFAULT ''",
            "ALTER TABLE products ADD COLUMN vendor_id INTEGER REFERENCES vendors(id) ON DELETE SET NULL",
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL UNIQUE, username TEXT DEFAULT '', notifications_enabled INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            "ALTER TABLE vendors ADD COLUMN allowed_delivery_methods TEXT DEFAULT 'delivery,pickup,post,deaddrop'",
            "ALTER TABLE products ADD COLUMN allowed_delivery_methods TEXT DEFAULT 'dead_drop,pickup,post,today'",
            "ALTER TABLE orders ADD COLUMN total REAL DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE orders ADD COLUMN location_id INTEGER REFERENCES dead_drop_locations(id) ON DELETE SET NULL",
            "CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, order_id INTEGER NOT NULL, user_id INTEGER NOT NULL, rating INTEGER DEFAULT 5, comment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL, FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE)",
            "CREATE TABLE IF NOT EXISTS product_variants (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, name TEXT NOT NULL, price REAL NOT NULL, FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE)",
            "ALTER TABLE cart_items ADD COLUMN variant_id INTEGER DEFAULT 0",
        ]
        for sql in migrations:
            try:
                await db.execute(sql)
            except aiosqlite.OperationalError:
                pass  # Column already exists

        await db.commit()
    finally:
        await db.close()
