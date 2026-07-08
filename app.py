from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "grocery-secret-key"

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://grocery_user:YOUR_PASSWORD@dpg-d96j1p7avr4c739jf2s0-a.ohio-postgres.render.com/grocery_4nr4"
)


def db():

    conn = psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )

    return conn

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        # مؤقتاً للتجربة
        if username == "admin" and password == "1234":

            session["user"] = "admin"
            return redirect(url_for("index"))


        elif username == "seller" and password == "1234":

            session["user"] = "seller"
            return redirect(url_for("seller"))


        else:
            return "اسم المستخدم أو كلمة المرور غير صحيحة"


    return render_template("login.html")
# ---------------- الصفحة الرئيسية ----------------

@app.route("/")
def index():

    if "user" not in session:
        return redirect(url_for("login"))

    if session["user"] == "seller":
        return redirect(url_for("seller"))

    conn = db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT 
            id,
            name,
            sale_price AS price,
            quantity AS qty
        FROM products
        ORDER BY name
    """)

    products = cur.fetchall()

    cur.close()
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

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO products
        (name, purchase_price, sale_price, quantity, barcode)
        VALUES (%s, %s, %s, %s, %s)
    """,
    (
        name,
        price,
        price,
        qty,
        ""
    ))

    conn.commit()

    cur.close()
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
        WHERE id=%s
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

    items = session.get("cart", [])

    print("CHECKOUT CART:")
    print(items)

    if not items:
        return "السلة فارغة"


    conn = db()

    cur = conn.cursor()

    for item in items:

        cur.execute("""
            UPDATE products
            SET quantity = quantity - %s
            WHERE id=%s
        """,
        (
            item["qty"],
            item["id"]
        ))

    conn.commit()

    cur.close()
    conn.close()


    total = sum(
        item["total"]
        for item in items
    )


    print("TOTAL:")
    print(total)
    total = sum(item["total"] for item in items)
    session["cart"] = []
    return render_template(
        "invoice.html",
        items=items,
        total=total,
        time=datetime.now()
    )
@app.route("/seller")
def seller():

    if session.get("user") != "seller":
        return redirect(url_for("login"))

    conn = db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT 
            id,
            name,
            sale_price AS price,
            quantity AS qty
        FROM products
        ORDER BY name
    """)

    products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "seller.html",
        products=products
    )
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

# ---------------- تشغيل ----------------

if __name__ == "__main__":

    app.run(debug=True)
