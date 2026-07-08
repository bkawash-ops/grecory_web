import psycopg2

DATABASE_URL = "postgresql://grocery_user:QzcYfUT5il61gzI8tdaihu1NvfGVjJ0S@dpg-d96j1p7avr4c739jf2s0-a.ohio-postgres.render.com/grocery_4nr4"

conn = psycopg2.connect(
    DATABASE_URL,
    sslmode="require"
)

cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name TEXT,
    purchase_price REAL DEFAULT 0,
    sale_price REAL DEFAULT 0,
    quantity REAL DEFAULT 0,
    barcode TEXT
);
""")

conn.commit()

print("✅ Products table created successfully.")

cur.close()
conn.close()
