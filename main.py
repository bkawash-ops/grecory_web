# main.py
import os
import re
import sqlite3
import tkinter as tk
import pandas as pd
import arabic_reshaper
from tkinter import ttk, messagebox
from datetime import datetime, date
from tkcalendar import DateEntry
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from bidi.algorithm import get_display
from tkinter import filedialog
# -------------------- إعداد المسارات والملفات --------------------
BASE_DIR = r"C:\Users\Yas\Desktop\Grecory_Sales"
os.makedirs(BASE_DIR, exist_ok=True)
REPORTS_DIR = os.path.join(BASE_DIR, "Reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, "supermarket.db")
AR_FONT_PATH = os.path.join(BASE_DIR, "arial.ttf")   # تأكد من وجود الملف أو عدّل المسار

# -------------------- إعداد قاعدة البيانات --------------------
conn = sqlite3.connect(DB_PATH, timeout=10)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    purchase_price REAL DEFAULT 0,
    sale_price REAL DEFAULT 0,
    quantity REAL DEFAULT 0,
    barcode TEXT UNIQUE
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT,
    total REAL,
    date_time TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER,
    product_id INTEGER,
    name TEXT,
    unit_price REAL,
    quantity REAL,
    total REAL
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    quantity REAL,
    total REAL,
    date_time TEXT
)
""")
conn.commit()

# -------------------- دوال مساعدة --------------------
def safe_float(x, default=0.0):
    try:
        return float(x)
    except:
        return default

def format_currency(x):
    try:
        return f"{float(x):.2f}"
    except:
        return "0.00"

def reshape_arabic(text):
    """إعادة تشكيل ونقل اتجاه النص العربي لليمين للعرض في PDF"""
    if text is None:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        bidi = get_display(reshaped)
        return bidi
    except Exception:
        return str(text)

def register_font():
    """تسجيل الخط العربي للاستخدام في reportlab (مرّة واحدة)"""
    try:
        pdfmetrics.registerFont(TTFont('ArabicFont', AR_FONT_PATH))
        return True
    except Exception as e:
        print("خط عربي غير مسجّل؛ تأكد من وجود arial.ttf في المسار:", AR_FONT_PATH, " - ", e)
        return False

_font_ok = register_font()

# أنماط Paragraph
styles = getSampleStyleSheet()
arabic_par_style = ParagraphStyle(
    name='Arabic',
    parent=styles['Normal'],
    fontName='ArabicFont' if _font_ok else 'Helvetica',
    fontSize=11,
    leading=13,
    alignment=2  # right
)
arabic_title_style = ParagraphStyle(
    name='ArabicTitle',
    parent=styles['Title'],
    fontName='ArabicFont' if _font_ok else 'Helvetica',
    fontSize=16,
    leading=20,
    alignment=2
)

# -------------------- واجهة المستخدم --------------------
root = tk.Tk()
root.title("نظام البقالة والسوبر ماركت - احترافي")
root.state("zoomed")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

# -------------------- تبويب المخزون --------------------
tab_stock = ttk.Frame(notebook)
notebook.add(tab_stock, text="المخزون")

frame_stock_top = tk.Frame(tab_stock)
frame_stock_top.pack(fill="x", padx=8, pady=6)

tk.Label(frame_stock_top, text="اسم المنتج").grid(row=0, column=0, padx=6)
entry_name = tk.Entry(frame_stock_top, width=30); entry_name.grid(row=0, column=1, padx=6)
tk.Label(frame_stock_top, text="سعر الشراء").grid(row=0, column=2, padx=6)
entry_purchase = tk.Entry(frame_stock_top, width=12); entry_purchase.grid(row=0, column=3, padx=6)
tk.Label(frame_stock_top, text="الكمية").grid(row=0, column=4, padx=6)
entry_quantity = tk.Entry(frame_stock_top, width=8); entry_quantity.grid(row=0, column=5, padx=6)
tk.Label(frame_stock_top, text="الباركود").grid(row=0, column=6, padx=6)
entry_barcode = tk.Entry(frame_stock_top, width=18); entry_barcode.grid(row=0, column=7, padx=6)

btn_add = tk.Button(frame_stock_top, text="إضافة المنتج", bg="#4CAF50", fg="white"); btn_add.grid(row=0, column=8, padx=6)
btn_delete = tk.Button(frame_stock_top, text="حذف المنتج", bg="#f44336", fg="white"); btn_delete.grid(row=0, column=9, padx=6)
btn_edit = tk.Button(frame_stock_top, text="تعديل المنتج", bg="#2196F3", fg="white"); btn_edit.grid(row=0, column=10, padx=6)
btn_print_stock = tk.Button(frame_stock_top, text="طباعة المخزون (PDF)", bg="#FF9800", fg="white"); btn_print_stock.grid(row=0, column=11, padx=6)

tree_products = ttk.Treeview(tab_stock, columns=("ID","Name","Purchase","Sale","Qty","Barcode"), show="headings")
tree_products.heading("ID", text="ID"); tree_products.column("ID", width=60, anchor="center")
tree_products.heading("Name", text="المنتج"); tree_products.column("Name", width=320)
tree_products.heading("Purchase", text="سعر الشراء"); tree_products.column("Purchase", width=120, anchor="e")
tree_products.heading("Sale", text="سعر البيع"); tree_products.column("Sale", width=120, anchor="e")
tree_products.heading("Qty", text="الكمية"); tree_products.column("Qty", width=100, anchor="center")
tree_products.heading("Barcode", text="الباركود"); tree_products.column("Barcode", width=180)
tree_products.pack(fill="both", expand=True, padx=8, pady=8)


# -------------------- زر استيراد من Excel --------------------

import pandas as pd
from tkinter import filedialog

def import_from_excel():
    try:
        file_path = filedialog.askopenfilename(title="اختر ملف Excel", filetypes=[("Excel files", "*.xlsx *.xls")])
        if not file_path:
            return
        df = pd.read_excel(file_path, engine='openpyxl')  # تأكد من استخدام openpyxl
        # التحقق من وجود الأعمدة المطلوبة
        required_columns = ["name", "purchase_price", "quantity", "barcode"]
        if not all(col in df.columns for col in required_columns):
            messagebox.showerror("خطأ", f"الملف يجب أن يحتوي على الأعمدة: {', '.join(required_columns)}")
            return
        for _, row in df.iterrows():
            name = str(row["name"]).strip()
            purchase = safe_float(row["purchase_price"])
            qty = safe_float(row["quantity"])
            barcode = str(row["barcode"]).strip()
            if not name:
                continue
            sale = round(purchase * 1.16, 2)
            try:
                c.execute("INSERT INTO products (name, purchase_price, sale_price, quantity, barcode) VALUES (?, ?, ?, ?, ?)",
                          (name, purchase, sale, qty, barcode))
            except sqlite3.IntegrityError:
                pass  # تخطي الباركود المكرر
        conn.commit()
        load_products()
        messagebox.showinfo("تم", "تم استيراد البيانات من Excel بنجاح")
    except Exception as e:
        messagebox.showerror("خطأ", f"حدث خطأ أثناء الاستيراد:\n{e}")

# إضافة الزر في واجهة المخزون بجانب الأزرار الأخرى
btn_import_excel = tk.Button(frame_stock_top, text="استيراد من Excel", bg="#8E44AD", fg="white", command=import_from_excel)
btn_import_excel.grid(row=0, column=12, padx=6)

# -------------------- تبويب البيع --------------------
tab_sales = ttk.Frame(notebook)
notebook.add(tab_sales, text="البيع")

frame_sales_top = tk.Frame(tab_sales)
frame_sales_top.pack(fill="x", padx=8, pady=6)

tk.Label(frame_sales_top, text="البحث بالباركود").grid(row=0, column=0, padx=6)
entry_sale_barcode = tk.Entry(frame_sales_top, width=22); entry_sale_barcode.grid(row=0, column=1, padx=6)
tk.Label(frame_sales_top, text="الكمية").grid(row=0, column=2, padx=6)
entry_sale_qty = tk.Entry(frame_sales_top, width=8); entry_sale_qty.grid(row=0, column=3, padx=6)
btn_add_sale = tk.Button(frame_sales_top, text="إضافة للبند", bg="#4CAF50", fg="white"); btn_add_sale.grid(row=0, column=4, padx=6)
btn_remove_sale = tk.Button(frame_sales_top, text="حذف بند", bg="#f44336", fg="white"); btn_remove_sale.grid(row=0, column=5, padx=6)
btn_finalize = tk.Button(frame_sales_top, text="إنهاء الفاتورة (PDF)", bg="#2196F3", fg="white"); btn_finalize.grid(row=0, column=6, padx=6)
btn_clear_sale = tk.Button(frame_sales_top, text="مسح الفاتورة الحالية", bg="#9E9E9E", fg="white"); btn_clear_sale.grid(row=0, column=7, padx=6)

tree_sale = ttk.Treeview(tab_sales, columns=("No","Name","Unit","Qty","Total"), show="headings")
tree_sale.heading("No", text="م"); tree_sale.column("No", width=50, anchor="center")
tree_sale.heading("Name", text="المنتج"); tree_sale.column("Name", width=300)
tree_sale.heading("Unit", text="سعر الوحدة"); tree_sale.column("Unit", width=120, anchor="e")
tree_sale.heading("Qty", text="الكمية"); tree_sale.column("Qty", width=80, anchor="center")
tree_sale.heading("Total", text="الإجمالي"); tree_sale.column("Total", width=120, anchor="e")
tree_sale.pack(fill="both", expand=True, padx=8, pady=8)

current_sale_items = []

# -------------------- تبويب التقارير --------------------
tab_reports = ttk.Frame(notebook)
notebook.add(tab_reports, text="التقارير")

frame_reports_top = tk.Frame(tab_reports)
frame_reports_top.pack(fill="x", padx=8, pady=6)

tk.Label(frame_reports_top, text="من تاريخ").grid(row=0, column=0, padx=6)
date_start = DateEntry(frame_reports_top, date_pattern='yyyy-MM-dd'); date_start.grid(row=0, column=1, padx=6)
tk.Label(frame_reports_top, text="إلى تاريخ").grid(row=0, column=2, padx=6)
date_end = DateEntry(frame_reports_top, date_pattern='yyyy-MM-dd'); date_end.grid(row=0, column=3, padx=6)
btn_gen_report = tk.Button(frame_reports_top, text="توليد التقرير (بين التواريخ)", bg="#4CAF50", fg="white"); btn_gen_report.grid(row=0, column=4, padx=6)

btn_daily = tk.Button(frame_reports_top, text="تقرير اليوم (PDF)", bg="#4CAF50", fg="white"); btn_daily.grid(row=0, column=5, padx=6)
btn_monthly = tk.Button(frame_reports_top, text="تقرير الشهر (PDF)", bg="#2196F3", fg="white"); btn_monthly.grid(row=0, column=6, padx=6)
btn_yearly = tk.Button(frame_reports_top, text="تقرير السنة (PDF)", bg="#FF9800", fg="white"); btn_yearly.grid(row=0, column=7, padx=6)

tree_reports = ttk.Treeview(tab_reports, columns=("Invoice","Date","Total"), show="headings")
tree_reports.heading("Invoice", text="رقم الفاتورة"); tree_reports.column("Invoice", width=180)
tree_reports.heading("Date", text="التاريخ"); tree_reports.column("Date", width=220)
tree_reports.heading("Total", text="المجموع"); tree_reports.column("Total", width=120, anchor="e")
tree_reports.pack(fill="both", expand=True, padx=8, pady=8)

# --------- إضافة ملصق يُظهر المجموع الكلي للفواتير في التقرير ---------
lbl_reports_total = tk.Label(tab_reports, text="المجموع الكلي للفواتير: 0.00", font=("Arial", 12, "bold"))
lbl_reports_total.pack(pady=6)

# -------------------- تحقق/تنبيهات المخزون المنخفض --------------------
LOW_STOCK_THRESHOLD = 2

def check_low_stock_and_alert(show_popup=True):
    rows = c.execute("SELECT name, quantity FROM products WHERE quantity <= ? ORDER BY id", (LOW_STOCK_THRESHOLD,)).fetchall()
    if rows:
        msg_lines = []
        for name, qty in rows:
            msg_lines.append(f"{name} — الكمية الحالية: {qty}")
        message = "تنبيه: المخزون منخفض للسلع التالية (<= {}):\n\n{}".format(LOW_STOCK_THRESHOLD, "\n".join(msg_lines))
        if show_popup:
            messagebox.showwarning("تنبيه المخزون المنخفض", message)
        return rows
    return []

# -------------------- التحقق من المدخلات (Validation) --------------------
def validate_letters(P):
    if P == "":
        return True
    return bool(re.fullmatch(r"^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FFa-zA-Z\s\-']*$", P))

def validate_numbers(P):
    if P == "":
        return True
    return bool(re.fullmatch(r"^\d*\.?\d*$", P))

def validate_barcode(P):
    if P == "":
        return True
    return bool(re.fullmatch(r"^[A-Za-z0-9\-]*$", P))

vcmd_letters = (root.register(validate_letters), '%P')
vcmd_numbers = (root.register(validate_numbers), '%P')
vcmd_barcode = (root.register(validate_barcode), '%P')

entry_name.config(validate='key', validatecommand=vcmd_letters)
entry_purchase.config(validate='key', validatecommand=vcmd_numbers)
entry_quantity.config(validate='key', validatecommand=vcmd_numbers)
entry_barcode.config(validate='key', validatecommand=vcmd_barcode)
entry_sale_qty.config(validate='key', validatecommand=vcmd_numbers)
entry_sale_barcode.config(validate='key', validatecommand=vcmd_barcode)

# -------------------- وظائف إدارة المخزون --------------------
def load_products():
    for i in tree_products.get_children():
        tree_products.delete(i)
    for row in c.execute("SELECT id, name, purchase_price, sale_price, quantity, barcode FROM products ORDER BY id"):
        tree_products.insert("", tk.END, values=row)
    check_low_stock_and_alert(show_popup=False)

def add_product():
    name = entry_name.get().strip()
    purchase = safe_float(entry_purchase.get())
    qty = safe_float(entry_quantity.get())
    barcode = entry_barcode.get().strip()
    if not name:
        messagebox.showerror("خطأ", "أدخل اسم المنتج (حروف فقط)")
        return
    sale = round(purchase * 1.16, 2)
    try:
        c.execute("INSERT INTO products (name, purchase_price, sale_price, quantity, barcode) VALUES (?, ?, ?, ?, ?)",
                  (name, purchase, sale, qty, barcode))
        conn.commit()
        load_products()
        entry_name.delete(0, tk.END); entry_purchase.delete(0, tk.END); entry_quantity.delete(0, tk.END); entry_barcode.delete(0, tk.END)
    except sqlite3.IntegrityError:
        messagebox.showerror("خطأ", "الباركود موجود مسبقًا")

def delete_product():
    sel = tree_products.selection()
    if not sel:
        messagebox.showwarning("تحذير", "اختر منتجًا للحذف")
        return
    if not messagebox.askyesno("تأكيد", "هل تريد حذف المنتج/المنتجات المحددة؟"):
        return
    for it in sel:
        pid = tree_products.item(it)["values"][0]
        c.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    load_products()

def edit_product():
    sel = tree_products.selection()
    if not sel:
        messagebox.showwarning("تحذير", "اختر منتجًا للتعديل")
        return
    pid = tree_products.item(sel[0])["values"][0]
    row = c.execute("SELECT id, name, purchase_price, sale_price, quantity, barcode FROM products WHERE id=?", (pid,)).fetchone()
    if not row:
        messagebox.showerror("خطأ", "المنتج غير موجود")
        return
    win = tk.Toplevel(root)
    win.title("تعديل المنتج")
    tk.Label(win, text="اسم المنتج").grid(row=0, column=0, padx=6, pady=6)
    name_e = tk.Entry(win, width=40); name_e.grid(row=0, column=1, padx=6, pady=6); name_e.insert(0, row[1])
    name_e.config(validate='key', validatecommand=vcmd_letters)
    tk.Label(win, text="سعر الشراء").grid(row=1, column=0, padx=6, pady=6)
    purchase_e = tk.Entry(win, width=20); purchase_e.grid(row=1, column=1, padx=6, pady=6); purchase_e.insert(0, str(row[2]))
    purchase_e.config(validate='key', validatecommand=vcmd_numbers)
    tk.Label(win, text="الكمية").grid(row=2, column=0, padx=6, pady=6)
    qty_e = tk.Entry(win, width=20); qty_e.grid(row=2, column=1, padx=6, pady=6); qty_e.insert(0, str(row[4]))
    qty_e.config(validate='key', validatecommand=vcmd_numbers)
    tk.Label(win, text="الباركود").grid(row=3, column=0, padx=6, pady=6)
    barcode_e = tk.Entry(win, width=30); barcode_e.grid(row=3, column=1, padx=6, pady=6); barcode_e.insert(0, row[5] if row[5] else "")
    barcode_e.config(validate='key', validatecommand=vcmd_barcode)

    def save_edit():
        name_new = name_e.get().strip()
        purchase_new = safe_float(purchase_e.get())
        qty_new = safe_float(qty_e.get())
        barcode_new = barcode_e.get().strip()
        if not name_new:
            messagebox.showerror("خطأ", "الاسم مطلوب")
            return
        sale_new = round(purchase_new * 1.16, 2)
        try:
            c.execute("UPDATE products SET name=?, purchase_price=?, sale_price=?, quantity=?, barcode=? WHERE id=?",
                      (name_new, purchase_new, sale_new, qty_new, barcode_new, pid))
            conn.commit()
            win.destroy()
            load_products()
        except sqlite3.IntegrityError:
            messagebox.showerror("خطأ", "الباركود مستخدم لمنتج آخر")

    tk.Button(win, text="حفظ", bg="#4CAF50", fg="white", command=save_edit).grid(row=4, column=0, columnspan=2, pady=8)

# -------------------- وظائف البيع --------------------
def add_sale_item():
    barcode = entry_sale_barcode.get().strip()
    qty = safe_float(entry_sale_qty.get(), 1)
    if not barcode:
        messagebox.showwarning("تحذير", "أدخل باركود المنتج")
        return
    row = c.execute("SELECT id, name, sale_price, quantity FROM products WHERE barcode=?", (barcode,)).fetchone()
    if not row:
        messagebox.showerror("خطأ", "الباركود غير موجود")
        return
    pid, name, price, stock_qty = row
    if qty <= 0:
        messagebox.showerror("خطأ", "أدخل كمية صحيحة أكبر من صفر")
        return
    if qty > stock_qty:
        messagebox.showerror("خطأ", f"الكمية المطلوبة أكبر من المخزون ({stock_qty})")
        return
    for it in current_sale_items:
        if it['product_id'] == pid:
            it['quantity'] += qty
            it['total'] = round(it['unit_price'] * it['quantity'], 2)
            refresh_sale_tree()
            entry_sale_barcode.delete(0, tk.END); entry_sale_qty.delete(0, tk.END)
            return
    total = round(price * qty, 2)
    current_sale_items.append({'product_id': pid, 'name': name, 'unit_price': price, 'quantity': qty, 'total': total})
    refresh_sale_tree()
    entry_sale_barcode.delete(0, tk.END); entry_sale_qty.delete(0, tk.END)

def refresh_sale_tree():
    for i in tree_sale.get_children():
        tree_sale.delete(i)
    for idx, it in enumerate(current_sale_items, 1):
        tree_sale.insert("", tk.END, values=(idx, it['name'], format_currency(it['unit_price']), it['quantity'], format_currency(it['total'])))

def remove_sale_item():
    sel = tree_sale.selection()
    if not sel:
        messagebox.showwarning("تحذير", "اختر بندًا للحذف")
        return
    idx = tree_sale.index(sel[0])
    current_sale_items.pop(idx)
    refresh_sale_tree()

def clear_sale():
    if not current_sale_items:
        return
    if not messagebox.askyesno("تأكيد", "مسح الفاتورة الحالية؟"):
        return
    current_sale_items.clear()
    refresh_sale_tree()

def finalize_invoice():
    if not current_sale_items:
        messagebox.showwarning("تحذير", "لا توجد بنود في الفاتورة")
        return
    invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    total_amount = round(sum(it['total'] for it in current_sale_items), 2)
    dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO invoices (invoice_number, total, date_time) VALUES (?, ?, ?)", (invoice_number, total_amount, dt_str))
    invoice_id = c.lastrowid
    for it in current_sale_items:
        c.execute("INSERT INTO invoice_items (invoice_id, product_id, name, unit_price, quantity, total) VALUES (?, ?, ?, ?, ?, ?)",
                  (invoice_id, it['product_id'], it['name'], it['unit_price'], it['quantity'], it['total']))
        # تحديث المخزون وسجل المبيعات
        c.execute("UPDATE products SET quantity = quantity - ? WHERE id=?", (it['quantity'], it['product_id']))
        c.execute("INSERT INTO sales (product_id, quantity, total, date_time) VALUES (?, ?, ?, ?)",
                  (it['product_id'], it['quantity'], it['total'], dt_str))
    conn.commit()
    generate_invoice_pdf_detailed(invoice_number, invoice_id, dt_str, current_sale_items, total_amount)
    os.startfile(os.path.join(REPORTS_DIR, f"{invoice_number}.pdf"))

    messagebox.showinfo("نجاح", f"تم إنشاء الفاتورة وحفظها في المجلد Reports\n{invoice_number}.pdf")
    current_sale_items.clear()
    refresh_sale_tree()
    load_products()
    check_low_stock_and_alert(show_popup=True)

# -------------------- توليد فاتورة PDF مفصّلة --------------------
def generate_invoice_pdf_detailed(invoice_number, invoice_id, dt_str, items, total_amount):
    filename = os.path.join(REPORTS_DIR, f"{invoice_number}.pdf")
    font_for_table = 'ArabicFont' if _font_ok else 'Helvetica'
    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30)
    elements = []
    elements.append(Paragraph(reshape_arabic("فاتورة بيع"), arabic_title_style))
    elements.append(Spacer(1, 8))
    header_table_data = [
        [Paragraph(reshape_arabic(f"رقم الفاتورة: {invoice_number}"), arabic_par_style),
         Paragraph(reshape_arabic(f"التاريخ: {dt_str}"), arabic_par_style)]
    ]
    header_table = Table(header_table_data, colWidths=[260, 260], hAlign='RIGHT')
    elements.append(header_table)
    elements.append(Spacer(1, 12))

    data = [[
        Paragraph(reshape_arabic("الإجمالي"), arabic_par_style),
        Paragraph(reshape_arabic("الكمية"), arabic_par_style),
        Paragraph(reshape_arabic("سعر الوحدة"), arabic_par_style),
        Paragraph(reshape_arabic("المنتج"), arabic_par_style),
        Paragraph(reshape_arabic("م"), arabic_par_style)
    ]]
    for idx, it in enumerate(items, 1):
        data.append([
            Paragraph(reshape_arabic(format_currency(it['total'])), arabic_par_style),
            Paragraph(reshape_arabic(str(it['quantity'])), arabic_par_style),
            Paragraph(reshape_arabic(format_currency(it['unit_price'])), arabic_par_style),
            Paragraph(reshape_arabic(it['name']), arabic_par_style),
            Paragraph(reshape_arabic(str(idx)), arabic_par_style)
        ])
    data.append([
        Paragraph(reshape_arabic(format_currency(total_amount)), arabic_par_style),
        '', '', Paragraph(reshape_arabic("المجموع الكلي"), arabic_par_style), ''
    ])
    table = Table(data, colWidths=[80, 60, 90, 240, 40], hAlign='RIGHT')
    table_style = TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2E86C1")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,-1), font_for_table),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('SPAN', (-4,-1), (-3,-1)),
    ])
    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(reshape_arabic("شكراً لتعاملكم معنا"), arabic_par_style))
    doc.build(elements)

# -------------------- طباعة تقرير المخزون (جدول منسق بالعربي) --------------------
def print_inventory_report_table():
    rows = c.execute("SELECT id, name, purchase_price, sale_price, quantity, barcode FROM products ORDER BY id").fetchall()
    if not rows:
        messagebox.showinfo("معلومة", "لا توجد منتجات للطباعة")
        return
    filename = os.path.join(REPORTS_DIR, f"مخزون_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf")
    font_for_table = 'ArabicFont' if _font_ok else 'Helvetica'
    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=40, bottomMargin=20)
    elements = []
    elements.append(Paragraph(reshape_arabic("تقرير المخزون - قائمة المنتجات"), arabic_title_style))
    elements.append(Spacer(1, 8))
    data = [[
        Paragraph(reshape_arabic("الباركود"), arabic_par_style),
        Paragraph(reshape_arabic("الكمية"), arabic_par_style),
        Paragraph(reshape_arabic("سعر البيع"), arabic_par_style),
        Paragraph(reshape_arabic("سعر الشراء"), arabic_par_style),
        Paragraph(reshape_arabic("المنتج"), arabic_par_style),
        Paragraph(reshape_arabic("م"), arabic_par_style)
    ]]
    for idx, r in enumerate(rows, 1):
        pid, name, purchase, sale, qty, barcode = r
        data.append([
            Paragraph(reshape_arabic(str(barcode)), arabic_par_style),
            Paragraph(reshape_arabic(str(qty)), arabic_par_style),
            Paragraph(reshape_arabic(format_currency(sale)), arabic_par_style),
            Paragraph(reshape_arabic(format_currency(purchase)), arabic_par_style),
            Paragraph(reshape_arabic(name), arabic_par_style),
            Paragraph(reshape_arabic(str(idx)), arabic_par_style)
        ])
    table = Table(data, colWidths=[90, 60, 80, 80, 190, 30], hAlign='RIGHT')
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#117A65")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,-1), font_for_table),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(table)
    doc.build(elements)
    os.startfile(filename)  # <-- فتح التقرير تلقائيًا
    messagebox.showinfo("تم", f"تم إنشاء تقرير المخزون وحفظه في:\n{filename}")

# -------------------- توليد تقارير المبيعات (يومي/شهري/سنوي/بين تواريخ) --------------------
def generate_sales_report(period="daily", start_date=None, end_date=None):
    if period == "range" and (start_date is None or end_date is None):
        messagebox.showerror("خطأ", "حدد تاريخ البداية والنهاية أولاً")
        return
    if period == "daily":
        s = date.today().strftime("%Y-%m-%d")
        rows = c.execute("SELECT id, invoice_number, total, date_time FROM invoices WHERE date(date_time)=?", (s,)).fetchall()
        title = f"تقرير المبيعات - اليوم ({s})"
    elif period == "monthly":
        s = date.today().strftime("%Y-%m")
        rows = c.execute("SELECT id, invoice_number, total, date_time FROM invoices WHERE substr(date_time,1,7)=?", (s,)).fetchall()
        title = f"تقرير المبيعات - الشهر ({s})"
    elif period == "yearly":
        s = date.today().strftime("%Y")
        rows = c.execute("SELECT id, invoice_number, total, date_time FROM invoices WHERE substr(date_time,1,4)=?", (s,)).fetchall()
        title = f"تقرير المبيعات - السنة ({s})"
    elif period == "range":
        start_s = start_date
        end_s = end_date
        rows = c.execute("SELECT id, invoice_number, total, date_time FROM invoices WHERE date(date_time) BETWEEN ? AND ? ORDER BY date_time", (start_s, end_s)).fetchall()
        title = f"تقرير المبيعات من {start_s} إلى {end_s}"
    else:
        rows = []
        title = "تقرير المبيعات"

    if not rows:
        messagebox.showinfo("معلومة", "لا توجد فواتير للفترة المحددة")
        tree_reports.delete(*tree_reports.get_children())
        lbl_reports_total.config(text="المجموع الكلي للفواتير: 0.00")
        return

    # تعبئة جدول الواجهة بالقيم
    tree_reports.delete(*tree_reports.get_children())
    total_sum = 0.0
    for r in rows:
        iid, inv_num, total, dt = r
        tree_reports.insert("", tk.END, values=(inv_num, dt, format_currency(total)))
        total_sum += safe_float(total)

    # عرض المجموع الكلي في واجهة البرنامج
    lbl_reports_total.config(text=f"المجموع الكلي للفواتير: {format_currency(total_sum)}")

    # تجهيز PDF للتقرير مع المجموع الكلي في أسفله
    filename = os.path.join(REPORTS_DIR, f"تقرير_مبيعات_{period}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf")
    font_for_table = 'ArabicFont' if _font_ok else 'Helvetica'
    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=20)
    elements = []
    elements.append(Paragraph(reshape_arabic(title), arabic_title_style))
    elements.append(Spacer(1, 8))

    # لكل فاتورة نعرض بياناتها كجدول صغير ثم نضيف فصل
    for inv in rows:
        inv_id, inv_num, inv_total, inv_dt = inv
        header = Paragraph(reshape_arabic(f"فاتورة رقم: {inv_num} — التاريخ: {inv_dt} — الإجمالي: {format_currency(inv_total)}"), arabic_par_style)
        elements.append(header); elements.append(Spacer(1,6))
        items = c.execute("SELECT name, unit_price, quantity, total FROM invoice_items WHERE invoice_id=? ORDER BY id", (inv_id,)).fetchall()
        data = [[
            Paragraph(reshape_arabic("الإجمالي"), arabic_par_style),
            Paragraph(reshape_arabic("الكمية"), arabic_par_style),
            Paragraph(reshape_arabic("سعر الوحدة"), arabic_par_style),
            Paragraph(reshape_arabic("المنتج"), arabic_par_style),
            Paragraph(reshape_arabic("م"), arabic_par_style)
        ]]
        for idx, it in enumerate(items, 1):
            name, unit_price, qty, tot = it
            data.append([
                Paragraph(reshape_arabic(format_currency(tot)), arabic_par_style),
                Paragraph(reshape_arabic(str(qty)), arabic_par_style),
                Paragraph(reshape_arabic(format_currency(unit_price)), arabic_par_style),
                Paragraph(reshape_arabic(name), arabic_par_style),
                Paragraph(reshape_arabic(str(idx)), arabic_par_style)
            ])
        table = Table(data, colWidths=[80, 60, 90, 240, 30], hAlign='RIGHT')
        table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.4, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A5276")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,-1), font_for_table),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # إضافة المجموع الكلي النهائي كفقرة بارزة في نهاية التقرير
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(reshape_arabic(f"المجموع الكلي لجميع الفواتير المدرجة: {format_currency(total_sum)}"), arabic_par_style))

    doc.build(elements)
    os.startfile(filename)  # <-- فتح التقرير تلقائيًا
    messagebox.showinfo("تم", f"تم إنشاء تقرير المبيعات وحفظه في:\n{filename}")


# -------------------- ربط الأزرار بالأحداث --------------------
btn_add.config(command=add_product)
btn_delete.config(command=delete_product)
btn_edit.config(command=edit_product)
btn_print_stock.config(command=print_inventory_report_table)

btn_add_sale.config(command=add_sale_item)
btn_remove_sale.config(command=remove_sale_item)
btn_clear_sale.config(command=clear_sale)
btn_finalize.config(command=finalize_invoice)

btn_gen_report.config(command=lambda: generate_sales_report("range", start_date=date_start.get_date().strftime("%Y-%m-%d"), end_date=date_end.get_date().strftime("%Y-%m-%d")))
btn_daily.config(command=lambda: generate_sales_report("daily"))
btn_monthly.config(command=lambda: generate_sales_report("monthly"))
btn_yearly.config(command=lambda: generate_sales_report("yearly"))

# -------------------- فحص المخزون المنخفض عند البدء --------------------
root.after(600, lambda: check_low_stock_and_alert(show_popup=True))

# -------------------- تشغيل الواجهة --------------------
load_products()
root.mainloop()
