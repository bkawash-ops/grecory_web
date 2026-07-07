from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = "supermarket.db"

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- HOME / POS ----------------
@app.route("/")
def index():
    conn = db()
    products = conn.execute("SELECT * FROM products").fetchall()
    return render_template("index.html", products=products)

# ---------------- ADD PRODUCT (بسيط) ----------------
@app.route("/add_product", methods=["POST"])
def add_product():
    name = request.form["name"]
    price = request.form["price"]
    qty = request.form["qty"]

    conn = db()
    conn.execute("INSERT INTO products(name, price, qty) VALUES (?, ?, ?)",
                 (name, price, qty))
    conn.commit()
    return redirect(url_for("index"))

# ---------------- CREATE INVOICE ----------------
@app.route("/create_invoice", methods=["POST"])
def create_invoice():
    product_id = request.form["product_id"]
    qty = float(request.form["qty"])

    conn = db()

    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()

    total = qty * product["price"]

    # تخفيض المخزون
    conn.execute("UPDATE products SET qty = qty - ? WHERE id=?",
                 (qty, product_id))

    conn.commit()

    return render_template("invoice.html",
                           product=product,
                           qty=qty,
                           total=total,
                           time=datetime.now())

if __name__ == "__main__":
    app.run(debug=True)
