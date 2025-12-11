from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import time

app = Flask(__name__)
app.secret_key = "change-this-secret"

# ---------- Paths / Config ----------
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


# ---------- DB INIT ----------
def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Students table (with all new fields)
    c.execute(
        """
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
        """
    )

    # Books table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            author TEXT,
            issued_to INTEGER,
            issue_date TEXT,
            return_date TEXT,
            FOREIGN KEY(issued_to) REFERENCES students(id)
        )
        """
    )

    # Fees table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            month TEXT,
            amount REAL,
            date_paid TEXT,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
        """
    )

    conn.commit()
    conn.close()


init_db()

# ---------- DASHBOARD ----------
@app.route("/")
def index():
    conn = get_conn()
    c = conn.cursor()

    # Active students only
    c.execute("SELECT COUNT(*) FROM students WHERE is_active = 1")
    total_students = c.fetchone()[0] or 0

    c.execute("SELECT COUNT(*) FROM students WHERE is_active = 0")
    old_students = c.fetchone()[0] or 0

    # c.execute("SELECT COUNT(*) FROM books")
    # total_books = c.fetchone()[0] or 0

    # c.execute("SELECT COUNT(*) FROM books WHERE issued_to IS NOT NULL")
    # issued_books = c.fetchone()[0] or 0

    c.execute("SELECT SUM(fee_amount) FROM students WHERE is_active = 1")
    total_fees = c.fetchone()[0] or 0

    conn.close()
    return render_template(
        "dashboard.html",
        total_students=total_students,
        old_students=old_students,
        total_fees=total_fees,
    )


# ---------- STUDENTS ----------
@app.route("/students")
def students():
    conn = get_conn()
    c = conn.cursor()
    # 💡 Explicit column order – indices fixed
    c.execute(
        """
        SELECT
            id,             -- 0
            name,           -- 1
            father,         -- 2
            phone,          -- 3
            address,        -- 4
            shift,          -- 5
            sheet_no,       -- 6
            admission_month,-- 7
            fee_amount,     -- 8
            aadhar_number,  -- 9
            admission_date, -- 10
            is_active,      -- 11
            aadhar_image    -- 12
        FROM students
        WHERE is_active = 1
        ORDER BY id DESC
        """
    )
    students = c.fetchall()
    conn.close()
    return render_template("students.html", students=students)


@app.route("/deleted_students")
def deleted_students():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        SELECT
            id,
            name,
            father,
            phone,
            address,
            shift,
            sheet_no,
            admission_month,
            fee_amount,
            aadhar_number,
            admission_date,
            is_active,
            aadhar_image
        FROM students
        WHERE is_active = 0
        ORDER BY id DESC
        """
    )
    students = c.fetchall()
    conn.close()
    return render_template("deleted_students.html", students=students)


def save_aadhar_file(file, old_filename=None):
    """Handle Aadhaar image upload, return stored filename (or old one)."""
    if file and file.filename and allowed_file(file.filename):
        # New file supplied
        filename = secure_filename(file.filename)
        unique_name = f"{int(time.time())}_{filename}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(file_path)
        return unique_name
    return old_filename


@app.route("/add_student", methods=["POST"])
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
    except ValueError:
        fee_amount = 0

    admission_date = datetime.now().strftime("%Y-%m-%d")

    file = request.files.get("aadhar_image")
    aadhar_image = save_aadhar_file(file)

    conn = get_conn()
    c = conn.cursor()

    # Auto-restore: check same phone or aadhar
    c.execute(
        """
        SELECT id, is_active, aadhar_image
        FROM students
        WHERE phone = ? OR aadhar_number = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (phone, aadhar_number),
    )
    row = c.fetchone()

    if row and row[1] == 0:
        # Restore existing inactive student
        student_id = row[0]
        old_image = row[2]

        if not aadhar_image:
            aadhar_image = old_image

        c.execute(
            """
            UPDATE students
            SET name=?, father=?, phone=?, address=?, shift=?,
                sheet_no=?, admission_month=?, fee_amount=?,
                aadhar_number=?, admission_date=?, is_active=1, aadhar_image=?
            WHERE id=?
            """,
            (
                name,
                father,
                phone,
                address,
                shift,
                sheet_no,
                admission_month,
                fee_amount,
                aadhar_number,
                admission_date,
                aadhar_image,
                student_id,
            ),
        )
    else:
        # New student
        c.execute(
            """
            INSERT INTO students
            (name, father, phone, address, shift, sheet_no,
             admission_month, fee_amount, aadhar_number,
             admission_date, is_active, aadhar_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                name,
                father,
                phone,
                address,
                shift,
                sheet_no,
                admission_month,
                fee_amount,
                aadhar_number,
                admission_date,
                aadhar_image,
            ),
        )

    conn.commit()
    conn.close()
    flash("Student saved successfully!", "success")
    return redirect(url_for("students"))


@app.route("/edit_student/<int:id>", methods=["POST"])
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
    except ValueError:
        fee_amount = 0

    conn = get_conn()
    c = conn.cursor()

    # Get old image
    c.execute("SELECT aadhar_image FROM students WHERE id = ?", (id,))
    row = c.fetchone()
    old_image = row[0] if row else None

    file = request.files.get("aadhar_image")
    aadhar_image = save_aadhar_file(file, old_filename=old_image)

    c.execute(
        """
        UPDATE students
        SET name=?, father=?, phone=?, address=?, shift=?,
            sheet_no=?, admission_month=?, fee_amount=?,
            aadhar_number=?, aadhar_image=?
        WHERE id=?
        """,
        (
            name,
            father,
            phone,
            address,
            shift,
            sheet_no,
            admission_month,
            fee_amount,
            aadhar_number,
            aadhar_image,
            id,
        ),
    )

    conn.commit()
    conn.close()
    flash("Student updated.", "success")
    return redirect(url_for("students"))


@app.route("/delete_student/<int:id>", methods=["POST"])
def delete_student(id):
    # Soft delete
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE students SET is_active = 0 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Student moved to old students.", "warning")
    return redirect(url_for("students"))


@app.route("/restore_student/<int:id>", methods=["POST"])
def restore_student(id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE students SET is_active = 1 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Student restored.", "success")
    return redirect(url_for("deleted_students"))


@app.route("/delete_student_permanent/<int:id>", methods=["POST"])
def delete_student_permanent(id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM students WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Student permanently deleted.", "danger")
    return redirect(url_for("deleted_students"))


# ---------- REPORTS ----------
@app.route("/reports")
def reports():
    conn = get_conn()
    c = conn.cursor()

    # Active students
    c.execute("SELECT COUNT(*) FROM students WHERE is_active = 1")
    total_students = c.fetchone()[0] or 0

    # Old (inactive) students
    c.execute("SELECT COUNT(*) FROM students WHERE is_active = 0")
    old_students = c.fetchone()[0] or 0

    # # Total books
    # c.execute("SELECT COUNT(*) FROM books")
    # total_books = c.fetchone()[0] or 0

    # # Issued books
    # c.execute("SELECT COUNT(*) FROM books WHERE issued_to IS NOT NULL")
    # issued_books = c.fetchone()[0] or 0

    # Total fees collected
    c.execute("SELECT SUM(fee_amount) FROM students WHERE is_active = 1")
    total_fees = c.fetchone()[0] or 0

    conn.close()
    return render_template(
        "reports.html",
        total_students=total_students,
        old_students=old_students,
        # total_books=total_books,
        # issued_books=issued_books,
        total_fees=total_fees,
    )




if __name__ == "__main__":
    app.run(debug=True)
