import psycopg2
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(
    DATABASE_URL,
    sslmode="require"
)

cur = conn.cursor()

cur.execute("""
ALTER TABLE products
ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;
""")

conn.commit()

print("Active column added successfully")

cur.close()
conn.close()
