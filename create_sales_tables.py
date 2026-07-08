import psycopg2

DATABASE_URL = "postgresql://grocery_user:QzcYfUT5il61gzI8tdaihu1NvfGVjJ0S@dpg-d96j1p7avr4c739jf2s0-a.ohio-postgres.render.com/grocery_4nr4"


conn = psycopg2.connect(
    DATABASE_URL,
    sslmode="require"
)

cur = conn.cursor()


cur.execute("""
CREATE TABLE IF NOT EXISTS sales (

    id SERIAL PRIMARY KEY,

    invoice_number INTEGER UNIQUE,

    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    username TEXT,

    total REAL DEFAULT 0

);
""")


conn.commit()
cur.execute("""
CREATE TABLE IF NOT EXISTS sale_items (

    id SERIAL PRIMARY KEY,

    sale_id INTEGER REFERENCES sales(id),

    product_id INTEGER,

    product_name TEXT,

    quantity REAL,

    purchase_price REAL,

    sale_price REAL,

    total REAL

);
""")

print("✅ sales table created successfully")


cur.close()
conn.close()
