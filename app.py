from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = "supermarket.db"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# فحص مؤقت لهيكل قاعدة البيانات
conn = db()

print("DATABASE TABLE:")
columns = conn.execute("PRAGMA table_info(products)").fetchall()

print("PRODUCT COLUMNS:")
for col in columns:
    print(dict(col))

conn.close()
# ---------------- الصفحة الرئيسية ----------------

@app.route("/")
def index():
    conn = db()

    products = conn.execute("""
        SELECT 
            id,
            name,
            sale_price AS price,
            quantity AS qty
        FROM products
        ORDER BY name
    """).fetchall()

    return render_template("index.html", products=products)


# ---------------- إضافة منتج ----------------

@app.route("/add_product", methods=["POST"])
def add_product():

    name = request.form["name"]
    price = float(request.form["price"])
    qty = float(request.form["qty"])

    conn = db()

    conn.execute("""
        INSERT INTO products
        (name, purchase_price, sale_price, quantity, barcode)
        VALUES (?, ?, ?, ?, ?)
    """, (
        name,
        price,
        price,
        qty,
        ""
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("index"))


# ---------------- إنشاء فاتورة ----------------

@app.route("/create_invoice", methods=["POST"])
def create_invoice():

    product_id = request.form["product_id"]
    qty = float(request.form["qty"])

    conn = db()

    product = conn.execute("""
        SELECT *
        FROM products
        WHERE id=?
    """, (product_id,)).fetchone()

    if product is None:
        conn.close()
        return "Product not found"

    if qty > product["quantity"]:
        conn.close()
        return "Not enough stock"

    total = qty * product["sale_price"]

    conn.execute("""
        UPDATE products
        SET quantity = quantity - ?
        WHERE id=?
    """, (qty, product_id))

    conn.commit()
    conn.close()

    return render_template(
        "invoice.html",
        product=product,
        qty=qty,
        total=total,
        time=datetime.now()
    )


if __name__ == "__main__":
    app.run(debug=True)
