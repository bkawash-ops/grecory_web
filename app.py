import os
import subprocess
from flask import Flask, render_template, request, redirect, url_for, session, flash
from io import BytesIO
from flask import send_file
from reportlab.pdfgen import canvas
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime 
from zoneinfo import ZoneInfo
from io import BytesIO
from flask import send_file 
from datetime import timedelta
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display
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
@app.route("/check_expenses_columns")
def check_expenses_columns():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='expenses'
    """)

    result = cur.fetchall()

    cur.close()
    conn.close()

    return str(result)
@app.route("/check_payment_column")
def check_payment_column():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT invoice_number, customer_name, payment_method
        FROM sales
        ORDER BY id DESC
        LIMIT 10
    """)

    data = cur.fetchall()

    cur.close()
    conn.close()

    return str(data)
@app.route("/customers")
def customers():

    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""

        SELECT

            c.id,
            c.name,
            c.phone,
            c.address,

            COUNT(DISTINCT s.id) AS invoices,

            COALESCE(SUM(s.total),0)::numeric AS sales_total,

            COALESCE(
                (
                    SELECT SUM(amount)
                    FROM customer_payments p
                    WHERE p.customer_id=c.id
                ),
                0
            )::numeric AS paid

        FROM customers c

        LEFT JOIN sales s
            ON s.customer_id=c.id

        GROUP BY
            c.id

        ORDER BY
            c.name

    """)

    customers = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "customers.html",
        customers=customers
    )

@app.route("/traders")
def traders():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            c.id,
            c.name,
            c.phone,
            SUM(d.amount) AS total_debt,
            SUM(d.paid) AS total_paid,
            SUM(d.amount - d.paid) AS remaining

        FROM customers c

        JOIN customer_debts d
        ON c.id = d.customer_id

        GROUP BY
            c.id,
            c.name,
            c.phone

        ORDER BY c.name
    """)

    traders = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "traders.html",
        traders=traders
    )
@app.route("/expense_report", methods=["GET", "POST"])
def expense_report():
    from_date = request.form.get("from_date", "")
    to_date = request.form.get("to_date", "")

    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)


    from_date = None
    to_date = None


    if request.method == "POST":

        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")


    if from_date and to_date:

        cur.execute("""
            SELECT
                expense_date,
                title,
                amount,
                username
            FROM expenses
            WHERE expense_date::date BETWEEN %s AND %s
            ORDER BY expense_date DESC
        """,
        (
            from_date,
            to_date
        ))

    else:

        cur.execute("""
            SELECT
                expense_date,
                title,
                amount,
                username
            FROM expenses
            ORDER BY expense_date DESC
        """)


    expenses = cur.fetchall()



    if from_date and to_date:

        cur.execute("""
            SELECT COALESCE(SUM(amount),0) AS total
            FROM expenses
            WHERE expense_date::date BETWEEN %s AND %s
        """,
        (
            from_date,
            to_date
        ))

    else:

        cur.execute("""
            SELECT COALESCE(SUM(amount),0) AS total
            FROM expenses
        """)



    total_expenses = cur.fetchone()["total"]



    cur.close()
    conn.close()


    return render_template(
        "expense_report.html",
        expenses=expenses,
        total_expenses=total_expenses,
        timedelta=timedelta,
        from_date=from_date,
        to_date=to_date
    )
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
    cur.execute("""
        SELECT COUNT(*) AS low_stock_count
        FROM products
        WHERE quantity <= 5
    """)

    low_stock_count = cur.fetchone()["low_stock_count"]
    cur.close()
    conn.close()
    notification_count = 0

    if low_stock_count > 0:
        notification_count += 1
    return render_template(
        "index.html",
        products=products,
        low_stock_count=low_stock_count,
        notification_count=notification_count
    )
@app.route("/reports_menu")
def reports_menu():

    if session.get("user") != "admin":
        return redirect(url_for("login"))

    return render_template("reports_menu.html")   

@app.route("/backup_page")
def backup_page():

    if session.get("user") != "admin":
        return redirect(url_for("login"))

    return render_template("backup.html")
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
            WHERE DATE(sale_date AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Amman')
                  BETWEEN %s AND %s
            ORDER BY id DESC
        """,
        (
            from_date,
            to_date
        ))

        sales = cur.fetchall()

        cur.execute("""
            SELECT
                COUNT(*) AS invoices_count,
                COALESCE(SUM(total),0) AS total_sales
            FROM sales
            WHERE DATE(
                sale_date AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Amman'
            ) BETWEEN %s AND %s
        """,
        (
            from_date,
            to_date
        ))
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
    if from_date and to_date:

        cur.execute("""
            SELECT
                COALESCE(SUM(
                    (si.sale_price - si.purchase_price) * si.quantity
                ),0) AS total_profit

            FROM sale_items si

            JOIN sales s
            ON si.sale_id = s.id

            WHERE DATE(
                s.sale_date AT TIME ZONE 'UTC'
                AT TIME ZONE 'Asia/Amman'
            )
            BETWEEN %s AND %s

        """,
        (
            from_date,
            to_date
        ))

    else:

        cur.execute("""
            SELECT
                COALESCE(SUM(
                    (sale_price - purchase_price) * quantity
                ),0) AS total_profit
            FROM sale_items
        """)


    profit = cur.fetchone()
    cur.close()
    conn.close()

    return render_template(
        "reports.html",
        sales=sales,
        summary=summary,
        profit=profit,
        from_date=from_date,
        to_date=to_date
    )
@app.route("/stock_movement_report", methods=["GET","POST"])
def stock_movement_report():

    if session.get("user") != "admin":
        return redirect(url_for("login"))


    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)


    # جلب الأصناف
    cur.execute("""
        SELECT id, name
        FROM products
        ORDER BY name
    """)

    products = cur.fetchall()


    movements = []
    selected_product = None
    current_stock = None

    total_sales = 0
    total_returns = 0
    net_movement = 0


    if request.method == "POST":

        product_id = request.form["product_id"]


        # بيانات الصنف
        cur.execute("""
            SELECT
                id,
                name,
                quantity
            FROM products
            WHERE id=%s
        """,
        (product_id,))


        selected_product = cur.fetchone()


        if selected_product:

            current_stock = selected_product["quantity"]


            cur.execute("""
                SELECT
                    movement_date,
                    movement_type,
                    quantity,
                    reference,
                    username
                FROM stock_movements
                WHERE product_id=%s
                ORDER BY movement_date DESC
            """,
            (product_id,))


            movements = cur.fetchall()
            for m in movements:

                if m["movement_type"] == "SALE":
                    total_sales += abs(float(m["quantity"]))

                elif m["movement_type"] == "RETURN":
                    total_returns += float(m["quantity"])


            net_movement = total_returns - total_sales


    cur.close()
    conn.close()


    return render_template(
        "stock_movement_report.html",
        products=products,
        movements=movements,
        selected_product=selected_product,
        current_stock=current_stock,
        total_sales=total_sales,
        total_returns=total_returns,
        net_movement=net_movement,
        timedelta=timedelta
    )
@app.route("/report_sellers", methods=["GET"])
def report_sellers():

    if session.get("user") != "admin":
        return redirect(url_for("login"))


    conn = db()

    cur = conn.cursor(cursor_factory=RealDictCursor)


    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")


    query = """
        SELECT
            username,
            COUNT(*) AS invoice_count,
            SUM(total) AS total_sales

        FROM sales

    """


    params = []


    if from_date and to_date:

        query += """
            WHERE sale_date::date BETWEEN %s AND %s
        """

        params.extend([
            from_date,
            to_date
        ])


    query += """
        GROUP BY username
        ORDER BY total_sales DESC
    """


    cur.execute(
        query,
        params
    )


    sellers = cur.fetchall()



    # الإجماليات

    total_invoices = sum(
        s["invoice_count"]
        for s in sellers
    )


    total_sales = sum(
        float(s["total_sales"])
        for s in sellers
    )


    cur.close()
    conn.close()



    return render_template(
        "report_sellers.html",
        sellers=sellers,
        total_invoices=total_invoices,
        total_sales=total_sales,
        from_date=from_date,
        to_date=to_date
    )
@app.route("/notifications")
def notifications():

    conn = db()
    cur = conn.cursor()


   # المنتجات الناقصة
    cur.execute("""
        SELECT *
        FROM products
        WHERE quantity <= 5
        ORDER BY quantity ASC
    """)

    low_stock_products = cur.fetchall()

    cur.close()
    conn.close()


    return render_template(
        "notifications.html",
        low_stock_products=low_stock_products
    )
@app.route("/profit_report")
def profit_report():

    if session.get("user") != "admin":
        return redirect(url_for("login"))


    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")


    conn = db()

    cur = conn.cursor(cursor_factory=RealDictCursor)


    total_sales = 0
    total_cost = 0
    total_profit = 0


    if from_date and to_date:

        cur.execute("""
            SELECT
                COALESCE(SUM(total),0) AS total_sales

            FROM sales

            WHERE DATE(
                sale_date AT TIME ZONE 'UTC'
                AT TIME ZONE 'Asia/Amman'
            )

            BETWEEN %s AND %s

        """,
        (
            from_date,
            to_date
        ))


        result = cur.fetchone()

        total_sales = result["total_sales"]
        cur.execute("""
            SELECT
                COALESCE(SUM(
                    purchase_price * quantity
                ),0) AS total_cost

            FROM sale_items si

            JOIN sales s
            ON si.sale_id = s.id

            WHERE DATE(
                s.sale_date AT TIME ZONE 'UTC'
                AT TIME ZONE 'Asia/Amman'
            )

            BETWEEN %s AND %s

        """,
        (
            from_date,
            to_date
        ))


        result = cur.fetchone()

        total_cost = result["total_cost"]    
        
    total_profit = total_sales - total_cost
    profit_details = []

    if from_date and to_date:

        cur.execute("""
            SELECT
                si.product_name,
                SUM(si.quantity) AS qty,
                SUM(si.total) AS sales,
                SUM(si.purchase_price * si.quantity) AS cost,
                SUM(
                    (si.sale_price - si.purchase_price) * si.quantity
                ) AS profit

            FROM sale_items si

            JOIN sales s
            ON si.sale_id = s.id

            WHERE DATE(
                s.sale_date AT TIME ZONE 'UTC'
                AT TIME ZONE 'Asia/Amman'
            )
            BETWEEN %s AND %s

            GROUP BY si.product_name

            ORDER BY profit DESC

        """,
        (
            from_date,
            to_date
        ))

        profit_details = cur.fetchall()
    cur.close()
    conn.close()

    
    return render_template(
        "profit_report.html",
        from_date=from_date,
        to_date=to_date,
        total_sales= "%.2f" % total_sales,
        total_cost="%.2f" % total_cost,
        total_profit="%.2f" % total_profit,
        profit_details=profit_details
    )

@app.route("/stock_report")
def stock_report():

    if session.get("user") != "admin":
        return redirect(url_for("login"))


    conn = db()

    cur = conn.cursor(cursor_factory=RealDictCursor)


    cur.execute("""
        SELECT
            p.name,

            p.quantity AS current_qty,
            (p.quantity * p.purchase_price) AS stock_value,
            COALESCE(
                SUM(si.quantity),
                0
            ) AS sold_qty,

            COALESCE(
                SUM(si.total),
                0
            ) AS sales_value


        FROM products p


        LEFT JOIN sale_items si

        ON p.id = si.product_id


        GROUP BY
            p.id


        ORDER BY
            p.name

    """)


    products = cur.fetchall()


    cur.close()
    conn.close()


    return render_template(
        "stock_report.html",
        products=products
    )

@app.route("/top_products_report")
def top_products_report():

    if session.get("user") != "admin":
        return redirect(url_for("login"))


    conn = db()

    cur = conn.cursor(cursor_factory=RealDictCursor)


    cur.execute("""
        SELECT

            si.product_name,

            COALESCE(
                SUM(si.quantity),
                0
            ) AS sold_qty,


            COUNT(
                DISTINCT si.sale_id
            ) AS invoices_count,


            COALESCE(
                SUM(si.total),
                0
            ) AS sales_value


        FROM sale_items si


        GROUP BY
            si.product_name


        ORDER BY
            sold_qty DESC

    """)


    products = cur.fetchall()


    cur.close()
    conn.close()


    return render_template(
        "top_products_report.html",
        products=products
    )

@app.route("/low_stock_report")
def low_stock_report():

    if session.get("user") != "admin":
        return redirect(url_for("login"))


    conn = db()

    cur = conn.cursor(cursor_factory=RealDictCursor)


    cur.execute("""
        SELECT

            id,
            name,
            quantity

        FROM products

        WHERE quantity <= 5

        ORDER BY quantity ASC

    """)


    products = cur.fetchall()


    cur.close()
    conn.close()


    return render_template(
        "low_stock_report.html",
        products=products,
        total_products=len(products)
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

    return redirect(url_for("products"))



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


    # التحقق إذا كان المنتج موجوداً في السلة

    found = False

    for item in cart:

        if item["id"] == product["id"]:

            item["qty"] += qty

            item["total"] = (
                item["qty"] *
                item["price"]
            )

            found = True
            break



    # إذا لم يكن موجوداً أضفه كسطر جديد

    if not found:

        cart.append({

            "id": product["id"],
            "name": product["name"],
            "price": product["sale_price"],
            "purchase_price": product["purchase_price"],
            "qty": qty,
            "total": qty * product["sale_price"]

        })


    session["cart"] = cart

    cur.close()
    conn.close()


    return redirect(url_for("seller"))

@app.route("/update_cart_qty", methods=["POST"])
def update_cart_qty():

    product_id = int(request.form["product_id"])
    action = request.form["action"]

    cart = session.get("cart", [])


    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)


    # جلب كمية المخزون الحالية
    cur.execute("""
        SELECT quantity
        FROM products
        WHERE id=%s
    """,
    (product_id,))


    product = cur.fetchone()


    cur.close()
    conn.close()



    for item in cart:


        if item["id"] == product_id:



            if action == "plus":


                # فحص المخزون قبل الزيادة
                if item["qty"] + 1 > product["quantity"]:

                    flash(
                        "⚠️ لا توجد كمية كافية في المخزون",
                        "warning"
                    )

                    return redirect(url_for("seller"))



                item["qty"] += 1



            elif action == "minus":


                item["qty"] -= 1



                if item["qty"] <= 0:

                    cart.remove(item)

                    break



            if item in cart:

                item["total"] = (
                    item["qty"] *
                    item["price"]
                )



            break



    session["cart"] = cart


    return redirect(url_for("seller"))
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

@app.route("/clear_cart", methods=["POST"])
def clear_cart():

    session["cart"] = []

    return redirect(url_for("seller"))

@app.route("/remove_from_cart", methods=["POST"])
def remove_from_cart():

    product_id = int(request.form["product_id"])

    cart = session.get("cart", [])

    cart = [
        item for item in cart
        if item["id"] != product_id
    ]

    session["cart"] = cart

    return redirect(url_for("seller"))
@app.route("/customer/<int:id>")
def customer_details(id):

    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)


    cur.execute("""
        SELECT *
        FROM customers
        WHERE id=%s
    """,
    (id,))

    customer = cur.fetchone()


    if not customer:
        return "العميل غير موجود"


    cur.execute("""
        SELECT
            invoice_number,
            sale_date,
            total
        FROM sales
        WHERE customer_id=%s
        ORDER BY id DESC
    """,
    (id,))

    invoices = cur.fetchall()


    cur.close()
    conn.close()


    return render_template(
        "customer_details.html",
        customer=customer,
        invoices=invoices
    )
# ---------------- إتمام البيع وطباعة الفاتورة ----------------

@app.route("/checkout", methods=["POST"])
def checkout():
    username = session.get("user")
    items = session.get("cart", [])
    customer_name = request.form.get("customer_name", "").strip()
    customer_phone = request.form.get("customer_phone", "").strip()
    customer_address = request.form.get("customer_address", "").strip()
    payment_method = request.form.get("payment_method", "CASH")
    print("PAYMENT METHOD =", payment_method)
    print("CHECKOUT CART:")
    print(items)

    if not items:
        return "السلة فارغة"

    print("ITEM DATA:")
    print(items)


    total = sum(
        item["total"]
        for item in items
    )
    
    sale_time = datetime.now(ZoneInfo("Asia/Amman"))
    conn = db()

    cur = conn.cursor()

    customer_id = None


    # إنشاء رقم فاتورة جديد
    cur.execute("""
        SELECT COALESCE(MAX(invoice_number),1000)+1
        FROM sales
    """)

    invoice_number = cur.fetchone()[0]


    if customer_name:


        cur.execute("""
            SELECT id
            FROM customers
            WHERE name=%s
            LIMIT 1
        """,
        (customer_name,))


        customer = cur.fetchone()


        if customer:

            customer_id = customer[0]


        else:


            cur.execute("""
                INSERT INTO customers
                (
                    name,
                    phone,
                    address
                )
                VALUES (%s,%s,%s)
                RETURNING id
            """,
            (
                customer_name,
                customer_phone,
                customer_address
            ))


            customer_id = cur.fetchone()[0]

        
        customer_id = None

        if customer_name:

            cur.execute("""
                SELECT id
                FROM customers
                WHERE name=%s
                LIMIT 1
            """,
            (customer_name,))

            customer = cur.fetchone()


            if customer:

                customer_id = customer[0]


            else:

                cur.execute("""
                    INSERT INTO customers
                    (
                        name,
                        phone,
                        address
                    )
                    VALUES (%s,%s,%s)
                    RETURNING id
                """,
                (
                    customer_name,
                    customer_phone,
                    customer_address
                ))

                customer_id = cur.fetchone()[0]
                customer_id = None
    # حفظ رأس الفاتورة
    cur.execute("""
        INSERT INTO sales
        (
            invoice_number,
            username,
            total,
            sale_date,
            customer_name,
            customer_phone,
            customer_address,
            customer_id
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """,
    (
        invoice_number,
        session.get("user"),
        total,
        sale_time,
        customer_name,
        customer_phone,
        customer_address,
        customer_id
    ))


    sale_id = cur.fetchone()[0]

    if payment_method == "CREDIT" and customer_id:

        cur.execute("""
            INSERT INTO customer_debts
            (
                customer_id,
                invoice_id,
                amount
            )
            VALUES (%s,%s,%s)
        """,
        (
            customer_id,
            sale_id,
            total
        ))

    # حفظ تفاصيل الفاتورة + خصم المخزون

    for item in items:

        cur.execute("""
            INSERT INTO sale_items
            (
                sale_id,
                product_id,
                product_name,
                quantity,
                purchase_price,
                sale_price,
                total
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            sale_id,
            item["id"],
            item["name"],
            item["qty"],
            item["purchase_price"],
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

        cur.execute("""
            INSERT INTO stock_movements
            (
                product_id,
                product_name,
                movement_type,
                quantity,
                reference,
                username
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """,
        (
            item["id"],
            item["name"],
            "SALE",
            -item["qty"],
            f"Invoice #{invoice_number}",
            username
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
        username=session.get("user"),
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_address=customer_address,
        payment_method=payment_method
    )
@app.route("/add_payment_method_column")
def add_payment_method_column():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        ALTER TABLE sales
        ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20)
    """)

    # جعل الفواتير القديمة كاش حتى لا تظهر كذمم
    cur.execute("""
        UPDATE sales
        SET payment_method='CASH'
        WHERE payment_method IS NULL
    """)

    conn.commit()

    cur.close()
    conn.close()

    return "payment_method column added successfully"
@app.route("/create_customer_payments")
def create_customer_payments():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS customer_payments
        (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            amount NUMERIC(10,2) NOT NULL,
            notes TEXT,
            username VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    cur.close()
    conn.close()

    return "customer_payments created successfully"


@app.route("/check_customers")
def check_customers():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM customers
        ORDER BY id DESC
    """)

    data = cur.fetchall()

    cur.close()
    conn.close()

    return str(data)

@app.route("/check_sales_customer")
def check_sales_customer():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            invoice_number,
            customer_name,
            customer_id
        FROM sales
        ORDER BY id DESC
        LIMIT 5
    """)

    data = cur.fetchall()

    cur.close()
    conn.close()

    return str(data)
@app.route("/invoices")
def invoices():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            invoice_number,
            username,
            total,
            sale_date
        FROM sales
        ORDER BY id DESC
    """)

    invoices = cur.fetchall()

    cur.close()
    conn.close()


    return render_template(
        "invoices.html",
        invoices=invoices,
        timedelta=timedelta
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
    # جلب المرتجعات الخاصة بالفاتورة

    cur.execute("""
        SELECT
            product_name,
            quantity,
            total
        FROM return_items
        WHERE return_id IN
        (
            SELECT id
            FROM returns
            WHERE invoice_number=%s
        )
    """,
    (invoice_number,))

    returns = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
    "invoice_details.html",
    sale=sale,
    items=items,
    returns=returns,
    timedelta=timedelta
    )

@app.route("/reports/pdf")
def reports_pdf():

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
                sale_date AT TIME ZONE 'UTC'
                AT TIME ZONE 'Asia/Amman' AS sale_date,
                username,
                total
            FROM sales
            WHERE DATE(
                sale_date AT TIME ZONE 'UTC'
                AT TIME ZONE 'Asia/Amman'
            )
            BETWEEN %s AND %s
            ORDER BY id DESC
        """,
        (
            from_date,
            to_date
        ))

    else:

        cur.execute("""
            SELECT
                invoice_number,
                sale_date AT TIME ZONE 'UTC'
                AT TIME ZONE 'Asia/Amman' AS sale_date,
                username,
                total
            FROM sales
            ORDER BY id DESC
        """)


    sales = cur.fetchall()


    cur.close()
    conn.close()



    pdf = BytesIO()


    font_path = os.path.join(
    app.root_path,
    "fonts",
    "DejaVuSans.ttf"
    )


    pdfmetrics.registerFont(
        TTFont(
            "Arabic",
            font_path
        )
    )


    c = canvas.Canvas(pdf)


    width, height = c._pagesize


    y = height - 50



    c.setFont(
        "Arabic",
        18
    )


    title = "زاد البيت - تقرير المبيعات"


    c.drawRightString(
        width-50,
        y,
        title
    )


    y -= 40


    c.setFont(
        "Arabic",
        12
    )


    if from_date and to_date:

        period = f"الفترة من {from_date} الى {to_date}"

        period = get_display(
            arabic_reshaper.reshape(period)
        )

        c.drawRightString(
            width-50,
            y,
            period
        )

        y -= 30



    count = len(sales)


    total_sales = sum(
        float(s["total"])
        for s in sales
    )


    text = f"عدد الفواتير: {count}     إجمالي المبيعات: {total_sales:.2f} JOD"


    text = get_display(
        arabic_reshaper.reshape(text)
    )


    c.drawRightString(
        width-50,
        y,
        text
    )


    y -= 50



    # عناوين الجدول

    headers = [
        "رقم الفاتورة",
        "التاريخ",
        "البائع",
        "المبلغ"
    ]


    x_positions = [
        60,
        180,
        350,
        480
    ]


    c.setFont(
        "Arabic",
        11
    )


    for i,h in enumerate(headers):

        c.drawString(
            x_positions[i],
            y,
            h
        )


    y -= 25



    for s in sales:


        date = s["sale_date"].strftime(
            "%Y-%m-%d %H:%M"
        )


        row = [

            str(s["invoice_number"]),
            date,
            s["username"],
            f"{float(s['total']):.2f} JOD"

        ]


        for i,value in enumerate(row):

            c.drawString(
                x_positions[i],
                y,
                str(value)
            )


        y -= 22



        if y < 50:

            c.showPage()

            y = height - 50



    y -= 30


    footer = "شكراً لتسوقكم معنا 🌹"


    footer = get_display(
        arabic_reshaper.reshape(footer)
    )


    c.setFont(
        "Arabic",
        12
    )


    c.drawCentredString(
        width/2,
        y,
        footer
    )


    c.save()


    pdf.seek(0)


    return send_file(
        pdf,
        download_name="تقرير_المبيعات.pdf",
        as_attachment=True
    )
@app.route("/backup")
def backup():

    if session.get("user") != "admin":
        return redirect(url_for("login"))


    backup_file = "grocery_backup.sql"


    database_url = DATABASE_URL


    command = [
        "pg_dump",
        database_url,
        "-f",
        backup_file
    ]


    try:

        subprocess.run(
            command,
            check=True
        )


        return send_file(
            backup_file,
            as_attachment=True,
            download_name="grocery_backup.sql"
        )


    except Exception as e:

        return f"حدث خطأ أثناء النسخ الاحتياطي: {e}"

@app.route("/return_invoice/<int:invoice_number>", methods=["GET","POST"])
def return_invoice(invoice_number):

    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)


    # حفظ المرتجع
    if request.method == "POST":
        print("RETURN DATA:", dict(request.form), flush=True)

        sale_id = request.form["sale_id"]

        username = session.get("user")

        return_total = 0


        cur.execute("""
            INSERT INTO returns
            (
                sale_id,
                invoice_number,
                username,
                total
            )
            VALUES (%s,%s,%s,%s)
            RETURNING id
        """,
        (
            sale_id,
            invoice_number,
            username,
            0
        ))

        return_id = cur.fetchone()["id"]



        for key,value in request.form.items():

            if key.startswith("return_qty_"):


                product_id = key.replace("return_qty_","")

                qty = float(value)


                if qty > 0:


                    cur.execute("""
                        SELECT
                            name,
                            sale_price
                        FROM products
                        WHERE id=%s
                    """,
                    (product_id,))


                    product = cur.fetchone()


                    item_total = qty * float(product["sale_price"])


                    return_total += item_total
                    # التأكد أن كمية المرتجع لا تتجاوز كمية الفاتورة

                    cur.execute("""
                        SELECT quantity
                        FROM sale_items
                        WHERE sale_id=%s
                    AND product_id=%s
                    """,
                    (
                        sale_id,
                        product_id
                    ))

                    sold_item = cur.fetchone()


                    if not sold_item or qty > sold_item["quantity"]:

                        conn.rollback()

                        return "كمية الإرجاع أكبر من الكمية المباعة"

                    

                    # إعادة المخزون
                    cur.execute("""
                        UPDATE products
                        SET quantity = quantity + %s
                        WHERE id=%s
                    """,
                    (
                        qty,
                        product_id
                    ))

                    cur.execute("""
                         INSERT INTO stock_movements
                         (
                             product_id,
                             product_name,
                             movement_type,
                             quantity,
                             reference,
                             username
                         )
                         VALUES
                         (
                             %s,
                             %s,
                             %s,
                             %s,
                             %s,
                             %s
                         )
                     """,
                     (
                         product_id,
                         product["name"],
                         "RETURN",
                         qty,
                         f"Invoice #{invoice_number}",
                         username
                     ))

                    cur.execute("""
                        INSERT INTO return_items
                        (
                            return_id,
                            product_id,
                            product_name,
                            quantity,
                            sale_price,
                            total
                        )
                        VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        return_id,
                        product_id,
                        product["name"],
                        qty,
                        product["sale_price"],
                        item_total
                    ))



        cur.execute("""
            UPDATE returns
            SET total=%s
            WHERE id=%s
        """,
        (
            return_total,
            return_id
        ))


        conn.commit()

        cur.close()
        conn.close()


        return redirect(
            url_for(
                "invoice_details",
                invoice_number=invoice_number
            )
        )



    # عرض صفحة المرتجع (GET)

    cur.execute("""
        SELECT
            id,
            invoice_number,
            username,
            total,
            sale_date
        FROM sales
        WHERE invoice_number=%s
    """,
    (invoice_number,))


    sale = cur.fetchone()



    cur.execute("""
        SELECT
            product_id,
            product_name,
            quantity,
            sale_price,
            total
        FROM sale_items
        WHERE sale_id=%s
    """,
    (sale["id"],))


    items = cur.fetchall()



    cur.close()
    conn.close()


    return render_template(
        "return_invoice.html",
        sale=sale,
        items=items
    )

@app.route("/expenses", methods=["GET", "POST"])
def expenses():

    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":

        title = request.form["title"]
        amount = request.form["amount"]
        notes = request.form.get("notes")

        username = session.get("user")


        cur.execute("""
            INSERT INTO expenses
            (
                title,
                amount,
                notes,
                username
            )
            VALUES (%s,%s,%s,%s)
        """,
        (
            title,
            amount,
            notes,
            username
        ))


        conn.commit()
        conn.close()

        return redirect("/expenses")

    cur.execute("""
        SELECT
            id,
            expense_date,
            title,
            amount,
            notes,
            username
        FROM expenses
        ORDER BY expense_date DESC
    """)

    expenses_list = cur.fetchall()


    cur.execute("""
        SELECT COALESCE(SUM(amount),0) AS total
        FROM expenses
    """)

    total_expenses = cur.fetchone()["total"]


    cur.close()
    conn.close()


    return render_template(
        "expenses.html",
        expenses=expenses_list,
        total_expenses=total_expenses,
        timedelta=timedelta
    )
@app.route("/edit_expense/<int:id>", methods=["GET","POST"])
def edit_expense(id):

    conn = db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":

        cur.execute("""
            UPDATE expenses
            SET
                title=%s,
                amount=%s,
                notes=%s
            WHERE id=%s
        """,
        (
            request.form["title"],
            request.form["amount"],
            request.form["notes"],
            id
        ))

        conn.commit()

        cur.close()
        conn.close()

        return redirect("/expenses")


    cur.execute("""
        SELECT *
        FROM expenses
        WHERE id=%s
    """,
    (id,))

    expense = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "edit_expense.html",
        expense=expense
    )
@app.route("/delete_expense/<int:id>")
def delete_expense(id):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM expenses
        WHERE id=%s
    """,
    (id,))

    conn.commit()

    cur.close()
    conn.close()

    return redirect("/expenses")
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

# ---------------- تشغيل ----------------

if __name__ == "__main__":

    app.run(debug=True)
