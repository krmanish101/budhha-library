from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory,session
import sqlite3
from datetime import datetime
import os
from functools import wraps
from werkzeug.utils import secure_filename
import time

app = Flask(__name__)
app.secret_key = "change-this-secret-key"  # change for production
# -------Simple admin login credentials-----
ADMIN_USERNAME="pujan1234"
ADMIN_PASSWORD="Pujan@123@12"
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "library.db")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "aadhar_uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_conn():
    return sqlite3.connect(DB_PATH)

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            next_url=request.path
            return redirect(url_for("login",next=next_url))
        return view_func(*args,**kwargs)
    return wrapper
def init_db():
    conn = get_conn()
    c = conn.cursor()
    

    # students
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            father TEXT,
            phone TEXT,
            address TEXT,
            shift TEXT,
            sheet_no TEXT,
            admission_month TEXT,
            fee_amount REAL,
            aadhar_number TEXT,
            admission_date TEXT,
            is_active INTEGER DEFAULT 1,
            aadhar_image TEXT
        )
    """)

    # books
    c.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            author TEXT,
            issued_to INTEGER,
            issue_date TEXT,
            return_date TEXT,
            FOREIGN KEY(issued_to) REFERENCES students(id)
        )
    """)

    # fees
    c.execute("""
        CREATE TABLE IF NOT EXISTS fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            month TEXT,
            amount REAL,
            date_paid TEXT,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)

    conn.commit()
    conn.close()


init_db()
#-------------------Login/LogOut-----------
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        username=request.form.get("username","").strip()
        password=request.form.get("password","").strip()
        if username==ADMIN_USERNAME and password== ADMIN_PASSWORD:
            session["logged_in"]=True
            session["admin_name"]=username
            next_url=request.args.get("nect") or url_for("index")
            flash("Logged in Successfully.","success")
            return redirect(next_url)
        else:
            flash("Invalid Username and Password.","danger")
    return render_template("login.html")
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.","success")
    return  redirect(url_for("login"))   
        

# ---------- DASHBOARD ----------
@app.route("/")
@login_required
def index():
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM students WHERE is_active = 1")
    total_students = c.fetchone()[0] or 0

    c.execute("SELECT COUNT(*) FROM students WHERE is_active = 0")
    old_students = c.fetchone()[0] or 0

    c.execute("SELECT COUNT(*) FROM books")
    total_books = c.fetchone()[0] or 0

    c.execute("SELECT COUNT(*) FROM books WHERE issued_to IS NOT NULL")
    issued_books = c.fetchone()[0] or 0

    c.execute("SELECT COALESCE(SUM(fee_amount), 0) FROM students WHERE is_active=1")
    total_fees = c.fetchone()[0] or 0
    # ---- fees per month for chart ----
    
    conn.close()
    return render_template(
        "dashboard.html",
        total_students=total_students,
        old_students=old_students,
        total_books=total_books,
        issued_books=issued_books,
        total_fees=total_fees )
      


# ---------- STUDENTS (with filters) ----------
@app.route("/students")
@login_required
def students():
    conn = get_conn()
    c = conn.cursor()
    name = request.args.get("name", "").strip()
    filter_sheet = request.args.get("sheet_no", "").strip()
    filter_month = request.args.get("admission_month", "").strip()

    

    query = """
        SELECT
            id, name, father, phone, address, shift, sheet_no,
            admission_month, fee_amount, aadhar_number, admission_date,
            is_active, aadhar_image
        FROM students
        WHERE is_active = 1
    """
    params = []

    if name:
        query += " AND (LOWER(name) LIKE ? OR LOWER(father) LIKE ?)"
        like = f"%{name.lower()}%"
        params.extend([like, like])

    if filter_sheet:
        query += " AND sheet_no LIKE ?"
        params.append(filter_sheet + "%")

    if filter_month:
        query += " AND admission_month LIKE ?"
        params.append(filter_month + "%")

    query += " ORDER BY sheet_no ASC"

    c.execute(query, params)
    students = c.fetchall()
    conn.close()

    return render_template(
        "students.html",
        students=students,
        filter_name=name,
        filter_sheet=filter_sheet,
        filter_month=filter_month
    )


def save_aadhar_file(file, old_filename=None):
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_name = f"{int(time.time())}_{filename}"
        path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(path)
        return unique_name
    return old_filename


@app.route("/add_student", methods=["POST"])
@login_required
def add_student():
    name = request.form.get("name")
    father = request.form.get("father")
    phone = request.form.get("phone")
    address = request.form.get("address")
    shift = request.form.get("shift")
    sheet_no = request.form.get("sheet_no")
    admission_month = request.form.get("admission_month")
    fee_amount = request.form.get("fee_amount") or 0
    aadhar_number = request.form.get("aadhar_number")

    try:
        fee_amount = float(fee_amount)
    except Exception:
        fee_amount = 0

    admission_date = datetime.now().strftime("%Y-%m-%d")

    file = request.files.get("aadhar_image")
    aadhar_image = save_aadhar_file(file)

    conn = get_conn()
    c = conn.cursor()

    # auto-restore if exists with same phone or aadhar but inactive
    c.execute(
        "SELECT id, is_active, aadhar_image FROM students WHERE phone = ? OR aadhar_number = ? ORDER BY id DESC LIMIT 1",
        (phone, aadhar_number),
    )
    row = c.fetchone()
    if row and row[1] == 0:
        sid = row[0]
        old_image = row[2]
        if not aadhar_image:
            aadhar_image = old_image
        c.execute(
            """
            UPDATE students
            SET name=?, father=?, phone=?, address=?, shift=?, sheet_no=?,
                admission_month=?, fee_amount=?, aadhar_number=?, admission_date=?,
                is_active=1, aadhar_image=?
            WHERE id=?
            """,
            (name, father, phone, address, shift, sheet_no, admission_month, fee_amount, aadhar_number, admission_date, aadhar_image, sid),
        )
    else:
        c.execute(
            """
            INSERT INTO students
            (name, father, phone, address, shift, sheet_no, admission_month,
             fee_amount, aadhar_number, admission_date, is_active, aadhar_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (name, father, phone, address, shift, sheet_no, admission_month, fee_amount, aadhar_number, admission_date, aadhar_image),
        )

    conn.commit()
    conn.close()
    flash("Student saved.", "success")
    return redirect(url_for("students"))


@app.route("/edit_student/<int:id>", methods=["POST"])
@login_required
def edit_student(id):
    name = request.form.get("name")
    father = request.form.get("father")
    phone = request.form.get("phone")
    address = request.form.get("address")
    shift = request.form.get("shift")
    sheet_no = request.form.get("sheet_no")
    admission_month = request.form.get("admission_month")
    fee_amount = request.form.get("fee_amount") or 0
    aadhar_number = request.form.get("aadhar_number")

    try:
        fee_amount = float(fee_amount)
    except Exception:
        fee_amount = 0

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT aadhar_image FROM students WHERE id = ?", (id,))
    row = c.fetchone()
    old_img = row[0] if row else None

    file = request.files.get("aadhar_image")
    aadhar_image = save_aadhar_file(file, old_filename=old_img)

    c.execute(
        """
        UPDATE students
        SET name=?, father=?, phone=?, address=?, shift=?,
            sheet_no=?, admission_month=?, fee_amount=?, aadhar_number=?, aadhar_image=?
        WHERE id=?
        """,
        (name, father, phone, address, shift, sheet_no, admission_month, fee_amount, aadhar_number, aadhar_image, id),
    )
    conn.commit()
    conn.close()
    flash("Student updated.", "success")
    return redirect(url_for("students"))


@app.route("/delete_student/<int:id>", methods=["POST"])
@login_required
def delete_student(id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE students SET is_active = 0 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Student moved to old students.", "warning")
    return redirect(url_for("students"))


@app.route("/deleted_students")
@login_required
def deleted_students():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, name, father, phone, address, shift, sheet_no,
               admission_month, fee_amount, aadhar_number, admission_date, is_active, aadhar_image
        FROM students
        WHERE is_active = 0
        ORDER BY id DESC
    """)
    students = c.fetchall()
    conn.close()
    return render_template("deleted_students.html", students=students)


@app.route("/restore_student/<int:id>", methods=["POST"])
@login_required
def restore_student(id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE students SET is_active = 1 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Student restored.", "success")
    return redirect(url_for("deleted_students"))


# PERMANENT delete route name consistent with template
@app.route("/delete_student_permanent/<int:id>", methods=["POST"])
@login_required
def delete_student_permanent(id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM students WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Student permanently deleted.", "danger")
    return redirect(url_for("deleted_students"))


# ---------- BOOKS ----------
@app.route("/books")
@login_required
def books():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT b.id, b.title, b.author, s.name, b.issue_date, b.return_date
        FROM books b
        LEFT JOIN students s ON b.issued_to = s.id
        ORDER BY b.id DESC
    """)
    books = c.fetchall()
    conn.close()
    return render_template("books.html", books=books)


@app.route("/add_book", methods=["POST"])
@login_required
def add_book():
    title = request.form.get("title")
    author = request.form.get("author")
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO books (title, author) VALUES (?, ?)", (title, author))
    conn.commit()
    conn.close()
    return redirect(url_for("books"))


@app.route("/edit_book/<int:id>", methods=["POST"])
@login_required
def edit_book(id):
    title = request.form.get("title")
    author = request.form.get("author")
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE books SET title = ?, author = ? WHERE id = ?", (title, author, id))
    conn.commit()
    conn.close()
    return redirect(url_for("books"))


@app.route("/delete_book/<int:id>", methods=["POST"])
@login_required
def delete_book(id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM books WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("books"))


@app.route("/issue_book", methods=["POST"])
@login_required
def issue_book():
    book_id = request.form.get("book_id")
    student_id = request.form.get("student_id")
    issue_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE books SET issued_to=?, issue_date=?, return_date=NULL WHERE id=?", (student_id, issue_date, book_id))
    conn.commit()
    conn.close()
    return redirect(url_for("books"))


@app.route("/return_book/<int:id>", methods=["POST"])
@login_required
def return_book(id):
    return_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE books SET issued_to=NULL, return_date=? WHERE id=?", (return_date, id))
    conn.commit()
    conn.close()
    return redirect(url_for("books"))


# # ---------- FEES ----------
# @app.route("/fees")
# def fees():
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("""
#         SELECT fees.id, students.name, fees.month, fees.amount, fees.date_paid
#         FROM fees JOIN students ON fees.student_id = students.id
#         ORDER BY fees.date_paid DESC
#     """)
#     all_fees = c.fetchall()
#     c.execute("SELECT id, name FROM students WHERE is_active = 1")
#     students = c.fetchall()
#     conn.close()
#     return render_template("fees.html", fees=all_fees, students=students)


# @app.route("/add_fee", methods=["POST"])
# def add_fee():
#     student_id = request.form.get("student_id")
#     month = request.form.get("month")
#     amount = request.form.get("amount") or 0
#     try:
#         amount = float(amount)
#     except Exception:
#         amount = 0
#     date_paid = datetime.now().strftime("%Y-%m-%d")
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("INSERT INTO fees (student_id, month, amount, date_paid) VALUES (?, ?, ?, ?)", (student_id, month, amount, date_paid))
#     conn.commit()
#     conn.close()
#     flash("Fee recorded.", "success")
#     return redirect(url_for("fees"))


# # ---------- Student-wise fee history ----------
# @app.route("/student_fees/<int:student_id>")
# def student_fees(student_id):
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("SELECT name FROM students WHERE id = ?", (student_id,))
#     student = c.fetchone()
#     c.execute("SELECT month, amount, date_paid FROM fees WHERE student_id = ? ORDER BY date_paid DESC", (student_id,))
#     fees = c.fetchall()
#     c.execute("SELECT COALESCE(SUM(amount),0) FROM fees WHERE student_id = ?", (student_id,))
#     total_paid = c.fetchone()[0] or 0
#     conn.close()
#     return render_template("student_fees.html", student=student, fees=fees, total_paid=total_paid)


# ---------- REPORTS ----------
@app.route("/reports")
@login_required
def reports():
    try:
        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT COALESCE(COUNT(*),0) FROM students WHERE is_active = 1")
        total_students = c.fetchone()[0] or 0

        c.execute("SELECT COALESCE(COUNT(*),0) FROM students WHERE is_active = 0")
        old_students = c.fetchone()[0] or 0

        # safe: if books table missing, this will raise — we catch below
        c.execute("SELECT COALESCE(COUNT(*),0) FROM books")
        total_books = c.fetchone()[0] or 0

        c.execute("SELECT COALESCE(COUNT(*),0) FROM books WHERE issued_to IS NOT NULL")
        issued_books = c.fetchone()[0] or 0

        c.execute("SELECT COALESCE(SUM(fee_amount), 0) FROM students WHERE is_active = 1")
        total_fees = c.fetchone()[0] or 0

        conn.close()

        return render_template("reports.html",
                               total_students=total_students,
                               old_students=old_students,
                               total_books=total_books,
                               issued_books=issued_books,
                               total_fees=total_fees)

    except Exception as e:
        # log the error so you can copy it from pythonanywhere error log
        app.logger.exception("Error in reports view")
        # friendly message to user; devs check logs
        return "Server error: check logs for details", 500

# serve aadhar files if needed (static route exists but this is explicit)
@app.route('/aadhar_download/<filename>')
def aadhar_download(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
