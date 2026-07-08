from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from zoneinfo import ZoneInfo
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
            purchase_price,
            sale_price,
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
@app.route("/reports")
def reports():

    if session.get("user") != "admin":
        return redirect(url_for("login"))

    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if from_date and to_date:

       cur.execute("""
            SELECT
                invoice_number,
                sale_date AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Amman' AS sale_date,
                username,
                total
            FROM sales
            ORDER BY id DESC
        """)

        sales = cur.fetchall()

        cur.execute("""
            SELECT
                COUNT(*) AS invoices_count,
                COALESCE(SUM(total),0) AS total_sales
            FROM sales
            WHERE DATE(sale_date) BETWEEN %s AND %s
        """, (from_date, to_date))

    else:

        cur.execute("""
            SELECT
                invoice_number,
                sale_date AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Amman' AS sale_date,
                username,
                total
            FROM sales
            ORDER BY id DESC
        """)

        sales = cur.fetchall()

        cur.execute("""
            SELECT
                COUNT(*) AS invoices_count,
                COALESCE(SUM(total),0) AS total_sales
            FROM sales
        """)

    summary = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "reports.html",
        sales=sales,
        summary=summary,
        from_date=from_date,
        to_date=to_date
    )
@app.route("/products")
def products():

    if session.get("user") != "admin":
        return redirect(url_for("login"))

    conn = db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            id,
            name,
            purchase_price,
            sale_price,
            quantity AS qty
        FROM products
        ORDER BY name
        """)

    products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "products.html",
        products=products
    )


@app.route("/edit_product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    if session.get("user") != "admin":
        return redirect(url_for("login"))

    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":

        name = request.form["name"]
        price = request.form["price"]
        qty = request.form["qty"]

        cur.execute("""
            UPDATE products
            SET name=%s,
                sale_price=%s,
                quantity=%s
            WHERE id=%s
        """,
        (
            name,
            price,
            qty,
            id
        ))

        conn.commit()

        cur.close()
        conn.close()

        return redirect(url_for("products"))


    cur.execute("""
        SELECT
            id,
            name,
            sale_price AS price,
            quantity AS qty
        FROM products
        WHERE id=%s
    """,
    (id,)
    )

    product = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "edit_product.html",
        product=product
    )


@app.route("/delete_product/<int:id>")
def delete_product(id):

    if session.get("user") != "admin":
        return redirect(url_for("login"))

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM products
        WHERE id = %s
    """,
    (id,))

    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for("products"))
# ---------------- إضافة منتج للمخزون ----------------

@app.route("/add_product", methods=["POST"])
def add_product():

    name = request.form["name"]

    purchase_price = float(
        request.form["purchase_price"]
    )

    sale_price = float(
        request.form["sale_price"]
    )

    qty = float(
        request.form["qty"]
    )

    barcode = request.form.get("barcode", "")


    conn = db()

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO products
        (name, purchase_price, sale_price, quantity, barcode)
        VALUES (%s, %s, %s, %s, %s)
    """,
    (
        name,
        purchase_price,
        sale_price,
        qty,
        barcode
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

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM products
        WHERE id=%s
    """,
    (product_id,))

    product = cur.fetchone()


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

    cur.close()
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


    total = sum(
        item["total"]
        for item in items
    )

    sale_time = datetime.now(ZoneInfo("Asia/Amman"))
    conn = db()

    cur = conn.cursor()


    # إنشاء رقم فاتورة جديد
    cur.execute("""
        SELECT COALESCE(MAX(invoice_number),1000)+1
        FROM sales
    """)

    invoice_number = cur.fetchone()[0]


    # حفظ رأس الفاتورة
    cur.execute("""
        INSERT INTO sales
        (
            invoice_number,
            username,
            total,
            sale_date
        )
        VALUES (%s,%s,%s,%s)
        RETURNING id
    """,
    (
        invoice_number,
        session.get("user"),
        total,
        sale_time
    ))


    sale_id = cur.fetchone()[0]


    # حفظ تفاصيل الفاتورة + خصم المخزون

    for item in items:


        cur.execute("""
            INSERT INTO sale_items
            (
                sale_id,
                product_id,
                product_name,
                quantity,
                sale_price,
                total
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """,
        (
            sale_id,
            item["id"],
            item["name"],
            item["qty"],
            item["price"],
            item["total"]
        ))



        cur.execute("""
            UPDATE products
            SET quantity = quantity - %s
            WHERE id = %s
        """,
        (
            item["qty"],
            item["id"]
        ))



    conn.commit()


    cur.close()
    conn.close()



    session["cart"] = []


    return render_template(
        "invoice.html",
        items=items,
        total=total,
        time=datetime.now(ZoneInfo("Asia/Amman")),
        invoice_number=invoice_number,
        username=session.get("user")
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
            barcode,
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

@app.route("/invoice/<int:invoice_number>")
def invoice_details(invoice_number):

    if session.get("user") != "admin":
        return redirect(url_for("login"))

    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            invoice_number,
            sale_date,
            username,
            total,
            id
        FROM sales
        WHERE invoice_number=%s
    """,
    (invoice_number,)
    )

    sale = cur.fetchone()

    cur.execute("""
        SELECT
            product_name,
            quantity,
            sale_price,
            total
        FROM sale_items
        WHERE sale_id=%s
    """,
    (sale["id"],)
    )

    items = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "invoice_details.html",
        sale=sale,
        items=items
    )
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

# ---------------- تشغيل ----------------

if __name__ == "__main__":

    app.run(debug=True)
