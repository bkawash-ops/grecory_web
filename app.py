import os
import subprocess
from flask import Flask, render_template, request, redirect, url_for, session
from io import BytesIO
from flask import send_file
from reportlab.pdfgen import canvas
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime 
from zoneinfo import ZoneInfo
from io import BytesIO
from flask import send_file 

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
@app.route("/notifications")
def notifications():

    conn = get_db()
    cur = conn.cursor()


    # المنتجات الناقصة
    cur.execute("""
        SELECT *
        FROM products
        WHERE qty <= 5
        ORDER BY qty ASC
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

    print("ITEM DATA:")
    print(items)


    total = sum(
        item["total"]
        for item in items
    )
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
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

# ---------------- تشغيل ----------------

if __name__ == "__main__":

    app.run(debug=True)
