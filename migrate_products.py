import sqlite3
import psycopg2

# الاتصال بـ SQLite
sqlite_conn = sqlite3.connect("supermarket.db")
sqlite_conn.row_factory = sqlite3.Row

sqlite_cur = sqlite_conn.cursor()

# الاتصال بـ PostgreSQL
pg_conn = psycopg2.connect(
    "postgresql://grocery_user:QzcYfUT5il61gzI8tdaihu1NvfGVjJ0S@dpg-d96j1p7avr4c739jf2s0-a.ohio-postgres.render.com/grocery_4nr4",
    sslmode="require"
)

pg_cur = pg_conn.cursor()

# قراءة جميع المنتجات
products = sqlite_cur.execute("""
SELECT
    name,
    purchase_price,
    sale_price,
    quantity,
    barcode
FROM products
""").fetchall()

count = 0

for p in products:

    pg_cur.execute("""
        INSERT INTO products
        (
            name,
            purchase_price,
            sale_price,
            quantity,
            barcode
        )
        VALUES (%s,%s,%s,%s,%s)
    """,
    (
        p["name"],
        p["purchase_price"],
        p["sale_price"],
        p["quantity"],
        p["barcode"]
    ))

    count += 1

pg_conn.commit()

print(f"✅ تم نقل {count} منتج إلى PostgreSQL")

sqlite_conn.close()
pg_conn.close()
