from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "grocery-secret-key"

DB = "supermarket.db"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


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

    conn.close()

    return render_template(
        "index.html",
        products=products
    )


# ---------------- إضافة منتج للمخزون ----------------

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
    """,
    (
        name,
        price,
        price,
        qty,
        ""
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("index"))



# ---------------- إضافة للسلة ----------------

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():

    product_id = request.form["product_id"]
    qty = float(request.form["qty"])


    conn = db()

    product = conn.execute("""
        SELECT *
        FROM products
        WHERE id=?
    """,
    (product_id,)
    ).fetchone()


    if product is None:
        conn.close()
        return "المنتج غير موجود"


    if qty > product["quantity"]:
        conn.close()
        return "الكمية غير متوفرة"


    cart = session.get("cart", [])


    cart.append({

        "id": product["id"],
        "name": product["name"],
        "price": product["sale_price"],
        "qty": qty,
        "total": qty * product["sale_price"]

    })


    session["cart"] = cart


    conn.close()


    return redirect(url_for("cart"))



# ---------------- عرض السلة ----------------

@app.route("/cart")
def cart():

    items = session.get("cart", [])

    print("CART DATA:")
    print(items)

    total = sum(item["total"] for item in items)

    return render_template(
        "cart.html",
        items=items,
        total=total
    )


# ---------------- إتمام البيع وطباعة الفاتورة ----------------

@app.route("/checkout", methods=["POST"])
def checkout():

    print("CHECKOUT CART:")
    print(session.get("cart"))

    items = session.get("cart", [])


    if not items:
        return "السلة فارغة"


    conn = db()


    # خصم الكميات

    for item in items:

        conn.execute("""
            UPDATE products
            SET quantity = quantity - ?
            WHERE id=?
        """,
        (
            item["qty"],
            item["id"]
        ))


    conn.commit()
    conn.close()


    total = sum(
        item["total"]
        for item in items
    )


    session.pop("cart", None)


    return render_template(
        "invoice.html",
        items=items,
        total=total,
        time=datetime.now()
    )



# ---------------- تشغيل ----------------

if __name__ == "__main__":

    app.run(debug=True)
