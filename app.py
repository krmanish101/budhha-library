from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ---------- Upload Config ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'aadhar_uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------- Database Setup ----------
def init_db():
    os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
    conn = sqlite3.connect(os.path.join(BASE_DIR, 'database', 'library.db'))
    c = conn.cursor()

    # Students Table
    c.execute('''CREATE TABLE IF NOT EXISTS students (
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
                )''')

    # # Books Table
    # c.execute('''CREATE TABLE IF NOT EXISTS books (
    #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
    #                 title TEXT,
    #                 author TEXT,
    #                 issued_to INTEGER,
    #                 issue_date TEXT,
    #                 return_date TEXT,
    #                 FOREIGN KEY(issued_to) REFERENCES students(id)
    #             )''')

    # # Fees Table
    # c.execute('''CREATE TABLE IF NOT EXISTS fees (
    #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
    #                 student_id INTEGER,
    #                 month TEXT,
    #                 amount REAL,
    #                 date_paid TEXT,
    #                 FOREIGN KEY(student_id) REFERENCES students(id)
    #             )''')

    conn.commit()
    conn.close()


def get_db_path():
    return os.path.join(BASE_DIR, 'database', 'library.db')


init_db()

# ---------- DASHBOARD ----------
@app.route('/')
def index():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM students WHERE is_active = 1")
    total_students = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM students WHERE is_active = 0")
    inactive_students = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM books")
    total_books = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM books WHERE issued_to IS NOT NULL")
    issued_books = c.fetchone()[0]

    c.execute("SELECT SUM(fee_amount) FROM students WHERE is_active = 1")
    total_fees = c.fetchone()[0] or 0

    conn.close()
    return render_template(
        'dashboard.html',
        total_students=total_students,
        inactive_students=inactive_students,
        # total_books=total_books,
        # issued_books=issued_books,
        total_fees=total_fees
    )

# ---------- STUDENTS (ACTIVE) ----------
@app.route('/students')
def students():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE is_active = 1 ORDER BY id DESC")
    students = c.fetchall()
    conn.close()
    return render_template('students.html', students=students)

# ---------- ADD STUDENT (AUTO RESTORE + IMAGE UPLOAD) ----------
@app.route('/add_student', methods=['POST'])
def add_student():
    name = request.form['name']
    father = request.form['father']
    phone = request.form['phone']
    address = request.form['address']
    shift = request.form['shift']
    sheet_no = request.form['sheet_no']
    admission_month = request.form['admission_month']
    fee_amount = request.form['fee_amount']
    aadhar_number = request.form['aadhar_number']
    admission_date = datetime.now().strftime("%Y-%m-%d")

    file = request.files.get('aadhar_image')
    aadhar_image_filename = None

    # Handle image upload
    if file and file.filename != "" and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_name = datetime.now().strftime("%Y%m%d%H%M%S_") + filename
        file.save(os.path.join(UPLOAD_FOLDER, unique_name))
        aadhar_image_filename = unique_name

    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()

    # Auto-restore: check if same (name, phone) inactive student exists
    c.execute("""
        SELECT id, aadhar_image FROM students
        WHERE name = ? AND phone = ? AND is_active = 0
        ORDER BY id DESC LIMIT 1
    """, (name, phone))
    row = c.fetchone()

    if row:
        student_id, old_image = row

        # If new image uploaded, optionally could delete old image
        if aadhar_image_filename is None:
            aadhar_image_filename = old_image

        c.execute("""
            UPDATE students
            SET name = ?, father = ?, phone = ?, address = ?, shift = ?,
                sheet_no = ?, admission_month = ?, fee_amount = ?,
                aadhar_number = ?, admission_date = ?, is_active = 1,
                aadhar_image = ?
            WHERE id = ?
        """, (name, father, phone, address, shift, sheet_no,
              admission_month, fee_amount, aadhar_number,
              admission_date, aadhar_image_filename, student_id))
    else:
        # New student
        c.execute("""
            INSERT INTO students
            (name, father, phone, address, shift, sheet_no,
             admission_month, fee_amount, aadhar_number,
             admission_date, is_active, aadhar_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (name, father, phone, address, shift, sheet_no,
              admission_month, fee_amount, aadhar_number,
              admission_date, aadhar_image_filename))

    conn.commit()
    conn.close()
    return redirect(url_for('students'))

# ---------- EDIT STUDENT (WITH OPTIONAL IMAGE CHANGE) ----------
@app.route('/edit_student/<int:id>', methods=['POST'])
def edit_student(id):
    name = request.form['name']
    father = request.form['father']
    phone = request.form['phone']
    address = request.form['address']
    shift = request.form['shift']
    sheet_no = request.form['sheet_no']
    admission_month = request.form['admission_month']
    fee_amount = request.form['fee_amount']
    aadhar_number = request.form['aadhar_number']

    file = request.files.get('aadhar_image')
    aadhar_image_filename = None

    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()

    # Get current image
    c.execute("SELECT aadhar_image FROM students WHERE id = ?", (id,))
    row = c.fetchone()
    current_image = row[0] if row else None

    # If new file uploaded, save it; otherwise keep old
    if file and file.filename != "" and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_name = datetime.now().strftime("%Y%m%d%H%M%S_") + filename
        file.save(os.path.join(UPLOAD_FOLDER, unique_name))
        aadhar_image_filename = unique_name
    else:
        aadhar_image_filename = current_image

    c.execute("""
        UPDATE students
        SET name = ?, father = ?, phone = ?, address = ?, shift = ?,
            sheet_no = ?, admission_month = ?, fee_amount = ?,
            aadhar_number = ?, aadhar_image = ?
        WHERE id = ?
    """, (name, father, phone, address, shift, sheet_no,
          admission_month, fee_amount, aadhar_number,
          aadhar_image_filename, id))

    conn.commit()
    conn.close()
    return redirect(url_for('students'))

# ---------- SOFT DELETE ----------
@app.route('/delete_student/<int:id>', methods=['POST'])
def delete_student(id):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("UPDATE students SET is_active = 0 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('students'))

# ---------- DELETED (OLD) STUDENTS ----------
@app.route('/deleted_students')
def deleted_students():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE is_active = 0 ORDER BY id DESC")
    students = c.fetchall()
    conn.close()
    return render_template('deleted_students.html', students=students)

# ---------- RESTORE STUDENT ----------
@app.route('/restore_student/<int:id>', methods=['POST'])
def restore_student(id):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("UPDATE students SET is_active = 1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('deleted_students'))

# ---------- PERMANENT DELETE (ALSO REMOVE IMAGE FILE) ----------
@app.route('/permanent_delete_student/<int:id>', methods=['POST'])
def permanent_delete_student(id):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()

    # fetch image filename first
    c.execute("SELECT aadhar_image FROM students WHERE id = ?", (id,))
    row = c.fetchone()
    img = row[0] if row else None

    # delete db row
    c.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    conn.close()

    # delete file from disk
    if img:
        img_path = os.path.join(UPLOAD_FOLDER, img)
        try:
            if os.path.exists(img_path):
                os.remove(img_path)
        except Exception:
            pass

    return redirect(url_for('deleted_students'))



# ---------- REPORTS ----------
@app.route('/reports')
def reports():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM students WHERE is_active = 1")
    total_students = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM books")
    total_books = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM books WHERE issued_to IS NOT NULL")
    issued_books = c.fetchone()[0]

    c.execute("SELECT SUM(fee_amount) FROM students WHERE is_active = 1")
    old_student = c.fetchone()[0] or 0

    conn.close()
    return render_template('reports.html',
                           total_students=total_students,
                        #    total_books=total_books,
                        #    issued_books=issued_books,
                           old_student=old_student)


if __name__ == '__main__':
    app.run(debug=True)

# # from flask import Flask, render_template, request, redirect, url_for
# # import sqlite3
# # from datetime import datetime
# # import os
# # from werkzeug.utils import secure_filename

# # UPLOAD_FOLDER = os.path.join('static', 'aadhar_uploads')
# # os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# # ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# # app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# # def allowed_file(filename):
# #     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# from flask import Flask, render_template, request, redirect, url_for
# import sqlite3
# from datetime import datetime
# import os
# from werkzeug.utils import secure_filename

# app = Flask(__name__)

# # ---------- Upload Config ----------
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'aadhar_uploads')
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



# app = Flask(__name__)

# # ---------- Database Setup ----------
# def init_db():
#     os.makedirs("database", exist_ok=True)
#     conn = sqlite3.connect('database/library.db')
#     c = conn.cursor()

#     # Students Table (SOFT DELETE ENABLED)
#     c.execute('''CREATE TABLE IF NOT EXISTS students (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     name TEXT,
#                     father TEXT,
#                     phone TEXT,
#                     address TEXT,
#                     shift TEXT,
#                     sheet_no TEXT,                    
#                     admission_month TEXT,
#                     fee_amount REAL,
#                     aadhar_number INTEGER,                    
#                     admission_date TEXT,
#                     is_active INTEGER DEFAULT 1
#                 )''')

#     # Books Table
#     c.execute('''CREATE TABLE IF NOT EXISTS books (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     title TEXT,
#                     author TEXT,
#                     issued_to INTEGER,
#                     issue_date TEXT,
#                     return_date TEXT,
#                     FOREIGN KEY(issued_to) REFERENCES students(id)
#                 )''')

#     # Fees Table
#     c.execute('''CREATE TABLE IF NOT EXISTS fees (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     student_id INTEGER,
#                     month TEXT,
#                     amount REAL,
#                     date_paid TEXT,
#                     FOREIGN KEY(student_id) REFERENCES students(id)
#                 )''')

#     conn.commit()
#     conn.close()

# init_db()

# # ---------- DASHBOARD ----------
# @app.route('/')
# def index():
#     conn = sqlite3.connect('database/library.db')
#     c = conn.cursor()

#     c.execute("SELECT COUNT(*) FROM students WHERE is_active = 1")
#     total_students = c.fetchone()[0]

#     c.execute("SELECT COUNT(*) FROM students WHERE is_active = 0")
#     inactive_students = c.fetchone()[0]

#     c.execute("SELECT COUNT(*) FROM books")
#     total_books = c.fetchone()[0]

#     c.execute("SELECT COUNT(*) FROM books WHERE issued_to IS NOT NULL")
#     issued_books = c.fetchone()[0]

#     c.execute("SELECT SUM(fee_amount) FROM students WHERE is_active = 1")
#     total_fees = c.fetchone()[0] or 0

#     conn.close()
#     return render_template(
#         'dashboard.html',
#         total_students=total_students,
#         inactive_students=inactive_students,   # 👈 yeh naya
#         total_books=total_books,
#         issued_books=issued_books,
#         total_fees=total_fees
#     )


# # ---------- STUDENTS ----------
# @app.route('/students')
# def students():
#     conn = sqlite3.connect('database/library.db')
#     c = conn.cursor()
#     c.execute("SELECT * FROM students WHERE is_active = 1 ORDER BY sheet_no ASC")
#     students = c.fetchall()
#     conn.close()
#     return render_template('students.html', students=students)

# # @app.route('/add_student', methods=['POST'])
# # def add_student():
# #     name = request.form['name']
# #     father = request.form['father']
# #     phone = request.form['phone']
# #     address = request.form['address']
# #     shift = request.form['shift']
# #     sheet_no = request.form['sheet_no']    
# #     admission_month = request.form['admission_month']
# #     fee_amount = request.form['fee_amount']
# #     aadhar = request.form['aadhar_number']
# #     admission_date = datetime.now().strftime("%Y-%m-%d")

# #     conn = sqlite3.connect('database/library.db')
# #     c = conn.cursor()

# #     # 1) Check: kya ye student pehle se DELETED hai? (same name + phone)
# #     c.execute("""
# #         SELECT id FROM students
# #         WHERE name = ? AND phone = ? AND is_active = 0
# #         ORDER BY id DESC LIMIT 1
# #     """, (name, phone))
# #     row = c.fetchone()

# #     if row:
# #         # 2) Agar mila, to purana record RESTORE + UPDATE karo
# #         student_id = row[0]
# #         c.execute("""
# #             UPDATE students
# #             SET name = ?, father = ?, phone = ?, address = ?, shift = ?,
# #                 sheet_no = ?, admission_month = ?, fee_amount = ?, aadhar_number = ?, admission_date = ?, is_active = 1
# #             WHERE id = ?
# #         """, (name, father, phone, address, shift, sheet_no,admission_month, fee_amount, aadhar, admission_date, student_id))
# #     else:
# #         # 3) Nahi mila to naya student insert karo
# #         c.execute("""
# #             INSERT INTO students
# #             (name, father, phone, address, shift, sheet_no, admission_month, fee_amount, aadhar_number, admission_date, is_active)
# #             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
# #         """, (name, father, phone, address, shift, sheet_no, admission_month, fee_amount, aadhar, admission_date))

# #     conn.commit()
# #     conn.close()
# #     return redirect(url_for('students'))
# @app.route('/add_student', methods=['POST'])
# def add_student():
#     name = request.form['name']
#     father = request.form['father']
#     phone = request.form['phone']
#     address = request.form['address']
#     shift = request.form['shift']
#     sheet_no = request.form['sheet_no']
#     admission_month = request.form['admission_month']
#     fee_amount = request.form['fee_amount']
#     aadhar_number = request.form['aadhar_number']
#     admission_date = datetime.now().strftime("%Y-%m-%d")

#     # --- Aadhar photo file ---
#     file = request.files.get('aadhar_image')
#     aadhar_image_filename = None

#     if file and file.filename != "" and allowed_file(file.filename):
#         filename = secure_filename(file.filename)
#         # unique name (id nahi pata to timestamp laga lo)
#         unique_name = datetime.now().strftime("%Y%m%d%H%M%S_") + filename
#         file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
#         aadhar_image_filename = unique_name

#     conn = sqlite3.connect('database/library.db')
#     c = conn.cursor()
#     c.execute("""
#         INSERT INTO students
#         (name, father, phone, address, shift, sheet_no, admission_month,
#          fee_amount, aadhar_number, admission_date, is_active, aadhar_image)
#         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
#     """, (name, father, phone, address, shift, sheet_no, admission_month,
#           fee_amount, aadhar_number, admission_date, aadhar_image_filename))

#     conn.commit()
#     conn.close()
#     return redirect(url_for('students'))



# @app.route('/edit_student/<int:id>', methods=['POST'])
# def edit_student(id):
#     data = (
#         request.form['name'],
#         request.form['father'],
#         request.form['phone'],
#         request.form['address'],
#         request.form['shift'],
#         request.form['sheet_no'],
#         request.form['admission_month'],
#         request.form['fee_amount'],        
#         request.form['aadhar_number'],
#         id
#     )
#     conn = sqlite3.connect('database/library.db')
#     c = conn.cursor()
#     c.execute("""UPDATE students SET name=?, father=?, phone=?, address=?, shift=?, 
#                  sheet_no=?, admission_month=?, fee_amount=?, aadhar_number=? WHERE id=?""", data)
#     conn.commit()
#     conn.close()
#     return redirect(url_for('students'))

# # ---------- SOFT DELETE ----------
# @app.route('/delete_student/<int:id>', methods=['POST'])
# def delete_student(id):
#     conn = sqlite3.connect('database/library.db')
#     c = conn.cursor()
#     c.execute("UPDATE students SET is_active = 0 WHERE id=?", (id,))
#     conn.commit()
#     conn.close()
#     return redirect(url_for('students'))

# # ---------- DELETED STUDENTS ----------
# @app.route('/deleted_students')
# def deleted_students():
#     conn = sqlite3.connect('database/library.db')
#     c = conn.cursor()
#     c.execute("SELECT * FROM students WHERE is_active = 0 ORDER BY id DESC")
#     students = c.fetchall()
#     conn.close()
#     return render_template('deleted_students.html', students=students)

# # ---------- RESTORE STUDENT ----------
# @app.route('/restore_student/<int:id>', methods=['POST'])
# def restore_student(id):
#     conn = sqlite3.connect('database/library.db')
#     c = conn.cursor()
#     c.execute("UPDATE students SET is_active = 1 WHERE id=?", (id,))
#     conn.commit()
#     conn.close()
#     return redirect(url_for('deleted_students'))

# # ---------- PERMANENT DELETE (OPTIONAL) ----------
# @app.route('/permanent_delete_student/<int:id>', methods=['POST'])
# def permanent_delete_student(id):
#     conn = sqlite3.connect('database/library.db')
#     c = conn.cursor()
#     c.execute("DELETE FROM students WHERE id=?", (id,))
#     conn.commit()
#     conn.close()
#     return redirect(url_for('deleted_students'))

# # # ---------- BOOKS ROUTES ----------
# # @app.route('/books')
# # def books():
# #     conn = sqlite3.connect('database/library.db')
# #     c = conn.cursor()
# #     c.execute("""SELECT b.id, b.title, b.author, s.name, b.issue_date, b.return_date 
# #                  FROM books b 
# #                  LEFT JOIN students s ON b.issued_to = s.id""")
# #     books = c.fetchall()
# #     conn.close()
# #     return render_template('books.html', books=books)

# # @app.route('/add_book', methods=['POST'])
# # def add_book():
# #     title = request.form['title']
# #     author = request.form['author']
# #     conn = sqlite3.connect('database/library.db')
# #     c = conn.cursor()
# #     c.execute("INSERT INTO books (title, author) VALUES (?, ?)", (title, author))
# #     conn.commit()
# #     conn.close()
# #     return redirect(url_for('books'))

# # @app.route('/edit_book/<int:id>', methods=['POST'])
# # def edit_book(id):
# #     title = request.form['title']
# #     author = request.form['author']
# #     conn = sqlite3.connect('database/library.db')
# #     c = conn.cursor()
# #     c.execute("UPDATE books SET title=?, author=? WHERE id=?", (title, author, id))
# #     conn.commit()
# #     conn.close()
# #     return redirect(url_for('books'))

# # @app.route('/delete_book/<int:id>', methods=['POST'])
# # def delete_book(id):
# #     conn = sqlite3.connect('database/library.db')
# #     c = conn.cursor()
# #     c.execute("DELETE FROM books WHERE id=?", (id,))
# #     conn.commit()
# #     conn.close()
# #     return redirect(url_for('books'))

# # @app.route('/issue_book', methods=['POST'])
# # def issue_book():
# #     book_id = request.form['book_id']
# #     student_id = request.form['student_id']
# #     issue_date = datetime.now().strftime("%Y-%m-%d")

# #     conn = sqlite3.connect('database/library.db')
# #     c = conn.cursor()
# #     c.execute("UPDATE books SET issued_to=?, issue_date=?, return_date=NULL WHERE id=?",
# #               (student_id, issue_date, book_id))
# #     conn.commit()
# #     conn.close()
# #     return redirect(url_for('books'))

# # @app.route('/return_book/<int:id>', methods=['POST'])
# # def return_book(id):
# #     return_date = datetime.now().strftime("%Y-%m-%d")

# #     conn = sqlite3.connect('database/library.db')
# #     c = conn.cursor()
# #     c.execute("UPDATE books SET issued_to=NULL, return_date=? WHERE id=?", (return_date, id))
# #     conn.commit()
# #     conn.close()
# #     return redirect(url_for('books'))

# # # ---------- FEES ----------
# # @app.route('/fees')
# # def fees():
# #     conn = sqlite3.connect('database/library.db')
# #     c = conn.cursor()
# #     c.execute("""SELECT fees.id, students.name, fees.month, fees.amount, fees.date_paid 
# #                  FROM fees 
# #                  JOIN students ON fees.student_id = students.id
# #                  WHERE students.is_active = 1
# #                  ORDER BY fees.date_paid DESC""")
# #     fees = c.fetchall()

# #     c.execute("SELECT id, name FROM students WHERE is_active = 0")
# #     students = c.fetchall()

# #     conn.close()
# #     return render_template('fees.html', fees=fees, students=students)

# # @app.route('/add_fee', methods=['POST'])
# # def add_fee():
# #     data = (
# #         request.form['student_id'],
# #         request.form['month'],
# #         request.form['amount'],
# #         datetime.now().strftime("%Y-%m-%d")
# #     )
# #     conn = sqlite3.connect('database/library.db')
# #     c = conn.cursor()
# #     c.execute("INSERT INTO fees (student_id, month, amount, date_paid) VALUES (?, ?, ?, ?)", data)
# #     conn.commit()
# #     conn.close()
# #     return redirect(url_for('fees'))

# # @app.route('/delete_fee/<int:id>', methods=['POST'])
# # def delete_fee(id):
# #     conn = sqlite3.connect('database/library.db')
# #     c = conn.cursor()
# #     c.execute("DELETE FROM fees WHERE id=?", (id,))
# #     conn.commit()
# #     conn.close()
# #     return redirect(url_for('fees'))

# # ---------- REPORTS ----------
# @app.route('/reports')
# def reports():
#     conn = sqlite3.connect('database/library.db')
#     c = conn.cursor()

#     c.execute("SELECT COUNT(*) FROM students WHERE is_active = 1")
#     total_students = c.fetchone()[0]
    
#     c.execute("SELECT COUNT(*) FROM students WHERE is_active = 0")
#     old_students = c.fetchone()[0]

#     c.execute("SELECT COUNT(*) FROM books")
#     total_books = c.fetchone()[0]

#     c.execute("SELECT COUNT(*) FROM books WHERE issued_to IS NOT NULL")
#     issued_books = c.fetchone()[0]

#     c.execute("SELECT SUM(fee_amount) FROM students WHERE is_active = 1")
#     total_fees = c.fetchone()[0] or 0

#     conn.close()
#     return render_template('reports.html',
#                            total_students=total_students,
#                            total_books=total_books,
#                            issued_books=issued_books,
#                            total_fees=total_fees,
#                            old_students=old_students)
    

# if __name__ == '__main__':
#     app.run(debug=True)



# students.html
# {% extends 'base.html' %}
# {% block title %}Students{% endblock %}

# {% block content %}
# <div class="container mt-4">
#     <h2 class="text-center mb-4">Student Management</h2>

#     <!-- Add Student Form -->
#     <div class="card mb-4 shadow-sm">
#         <div class="card-header bg-primary text-white">Add New Student</div>
#         <div class="card-body">
#             <form method="POST"
#                   action="{{ url_for('add_student') }}"
#                   enctype="multipart/form-data">
#                 <div class="row g-3">
#                     <div class="col-md-4">
#                         <input type="text" name="name" class="form-control"
#                                placeholder="Student Name" required>
#                     </div>
#                     <div class="col-md-4">
#                         <input type="text" name="father" class="form-control"
#                                placeholder="Father's Name" required>
#                     </div>
#                     <div class="col-md-4">
#                         <input type="text" name="phone" class="form-control"
#                                placeholder="Phone Number" required>
#                     </div>

#                     <div class="col-md-4">
#                         <input type="text" name="address" class="form-control"
#                                placeholder="Address">
#                     </div>
#                     <div class="col-md-2">
#                         <input type="text" name="shift" class="form-control"
#                                placeholder="Shift (e.g. 10 to 6)">
#                     </div>
#                     <div class="col-md-2">
#                         <input type="text" name="sheet_no" class="form-control"
#                                placeholder="Sheet No">
#                     </div>

#                     <!-- Admission Month dropdown -->
#                     <div class="col-md-2">
#                         <select name="admission_month" class="form-control" required>
#                             <option value="" disabled selected>Admission Month</option>
#                             <option>January</option>
#                             <option>February</option>
#                             <option>March</option>
#                             <option>April</option>
#                             <option>May</option>
#                             <option>June</option>
#                             <option>July</option>
#                             <option>August</option>
#                             <option>September</option>
#                             <option>October</option>
#                             <option>November</option>
#                             <option>December</option>
#                         </select>
#                     </div>

#                     <div class="col-md-2">
#                         <input type="number" step="0.01" name="fee_amount"
#                                class="form-control" placeholder="Fee Amount">
#                     </div>

#                     <div class="col-md-4">
#                         <input type="text" name="aadhar_number" class="form-control"
#                                placeholder="Aadhar Number">
#                     </div>

#                     <!-- Aadhar Photo Upload -->
#                     <div class="col-md-4">
#                         <input type="file" name="aadhar_image" class="form-control"
#                                accept="image/*">
#                     </div>
#                 </div>

#                 <div class="text-end mt-3">
#                     <button type="submit" class="btn btn-success">Add Student</button>
#                 </div>
#             </form>
#         </div>
#     </div>

#     <!-- Students Table -->
#     <div class="card shadow-sm">
#         <div class="card-header bg-dark text-white">Student Records</div>
#         <div class="card-body">
#             <div class="table-responsive">
#                 <table class="table table-bordered table-hover align-middle">
#                     <thead class="table-dark">
#                         <tr>
#                             <th>ID</th>
#                             <th>Name</th>
#                             <th>Father</th>
#                             <th>Phone</th>
#                             <th>Address</th>
#                             <th>Shift</th>
#                             <th>Sheet No</th>
#                             <th>Admission Month</th>
#                             <th>Fee Amount</th>
#                             <th>Aadhar</th>
#                             <th>Admission Date</th>
#                             <th>Actions</th>
#                         </tr>
#                     </thead>
#                     <tbody>
#                         {% for s in students %}
#                         <tr>
#                             <td>{{ s[0] }}</td>  <!-- ID -->
#                             <td>{{ s[1] }}</td>  <!-- Name -->
#                             <td>{{ s[2] }}</td>  <!-- Father -->
#                             <td>{{ s[3] }}</td>  <!-- Phone -->
#                             <td>{{ s[4] }}</td>  <!-- Address -->
#                             <td>{{ s[5] }}</td>  <!-- Shift -->
#                             <td>{{ s[6] }}</td>  <!-- Sheet No -->
#                             <td>{{ s[7] }}</td>  <!-- Admission Month -->
#                             <td>₹{{ "%.2f"|format(s[8] or 0) }}</td>  <!-- Fee Amount -->

#                             <!-- Aadhar Number + View Photo -->
#                             <td>
#                                 {{ s[9] }}  <!-- Aadhar Number -->

#                                 {% if s[12] %}
#                                     <br>
#                                     <a href="{{ url_for('static',
#                                             filename='aadhar_uploads/' ~ s[12]) }}"
#                                        target="_blank"
#                                        class="btn btn-sm btn-outline-primary mt-1">
#                                         View Photo
#                                     </a>
#                                 {% endif %}
#                             </td>

#                             <td>{{ s[10] }}</td> <!-- Admission Date -->

#                             <td>
#                                 <!-- Edit Button -->
#                                 <button class="btn btn-warning btn-sm"
#                                         data-bs-toggle="modal"
#                                         data-bs-target="#editModal{{ s[0] }}">
#                                     Edit
#                                 </button>

#                                 <!-- Delete Button -->
#                                 <form method="POST"
#                                       action="{{ url_for('delete_student', id=s[0]) }}"
#                                       style="display:inline-block;">
#                                     <button type="submit"
#                                             class="btn btn-danger btn-sm"
#                                             onclick="return confirm('Delete this student?')">
#                                         Delete
#                                     </button>
#                                 </form>
#                             </td>
#                         </tr>

#                         <!-- Edit Modal -->
#                         <div class="modal fade" id="editModal{{ s[0] }}" tabindex="-1"
#                              aria-hidden="true">
#                             <div class="modal-dialog modal-lg">
#                                 <div class="modal-content">
#                                     <form method="POST"
#                                           action="{{ url_for('edit_student', id=s[0]) }}"
#                                           enctype="multipart/form-data">
#                                         <div class="modal-header bg-primary text-white">
#                                             <h5 class="modal-title">Edit Student</h5>
#                                             <button type="button" class="btn-close"
#                                                     data-bs-dismiss="modal"></button>
#                                         </div>
#                                         <div class="modal-body">
#                                             <div class="row g-3">
#                                                 <div class="col-md-4">
#                                                     <label class="form-label">Name</label>
#                                                     <input type="text" name="name"
#                                                            class="form-control"
#                                                            value="{{ s[1] }}" required>
#                                                 </div>
#                                                 <div class="col-md-4">
#                                                     <label class="form-label">Father's Name</label>
#                                                     <input type="text" name="father"
#                                                            class="form-control"
#                                                            value="{{ s[2] }}" required>
#                                                 </div>
#                                                 <div class="col-md-4">
#                                                     <label class="form-label">Phone</label>
#                                                     <input type="text" name="phone"
#                                                            class="form-control"
#                                                            value="{{ s[3] }}" required>
#                                                 </div>

#                                                 <div class="col-md-4">
#                                                     <label class="form-label">Address</label>
#                                                     <input type="text" name="address"
#                                                            class="form-control"
#                                                            value="{{ s[4] }}">
#                                                 </div>
#                                                 <div class="col-md-2">
#                                                     <label class="form-label">Shift</label>
#                                                     <input type="text" name="shift"
#                                                            class="form-control"
#                                                            value="{{ s[5] }}">
#                                                 </div>
#                                                 <div class="col-md-2">
#                                                     <label class="form-label">Sheet No</label>
#                                                     <input type="text" name="sheet_no"
#                                                            class="form-control"
#                                                            value="{{ s[6] }}">
#                                                 </div>

#                                                 <div class="col-md-2">
#                                                     <label class="form-label">Admission Month</label>
#                                                     <select name="admission_month"
#                                                             class="form-control" required>
#                                                         {% set months = [
#                                                             'January','February','March','April',
#                                                             'May','June','July','August',
#                                                             'September','October','November','December'
#                                                         ] %}
#                                                         {% for m in months %}
#                                                             <option value="{{ m }}"
#                                                                 {% if s[7] == m %}selected{% endif %}>
#                                                                 {{ m }}
#                                                             </option>
#                                                         {% endfor %}
#                                                     </select>
#                                                 </div>

#                                                 <div class="col-md-2">
#                                                     <label class="form-label">Fee Amount</label>
#                                                     <input type="number" step="0.01"
#                                                            name="fee_amount"
#                                                            class="form-control"
#                                                            value="{{ s[8] }}">
#                                                 </div>

#                                                 <div class="col-md-4">
#                                                     <label class="form-label">Aadhar Number</label>
#                                                     <input type="text" name="aadhar_number"
#                                                            class="form-control"
#                                                            value="{{ s[9] }}">
#                                                 </div>

#                                                 <div class="col-md-4">
#                                                     <label class="form-label">
#                                                         Aadhar Photo
#                                                         <small class="text-muted">
#                                                             (leave empty to keep same)
#                                                         </small>
#                                                     </label>
#                                                     <input type="file" name="aadhar_image"
#                                                            class="form-control" accept="image/*">

#                                                     {% if s[12] %}
#                                                         <small>
#                                                             Current:
#                                                             <a href="{{ url_for('static',
#                                                                 filename='aadhar_uploads/' ~ s[12]) }}"
#                                                                target="_blank">
#                                                                 View
#                                                             </a>
#                                                         </small>
#                                                     {% endif %}
#                                                 </div>
#                                             </div>
#                                         </div>
#                                         <div class="modal-footer">
#                                             <button type="submit" class="btn btn-success">
#                                                 Save Changes
#                                             </button>
#                                             <button type="button" class="btn btn-secondary"
#                                                     data-bs-dismiss="modal">
#                                                 Close
#                                             </button>
#                                         </div>
#                                     </form>
#                                 </div>
#                             </div>
#                         </div>
#                         {% endfor %}
#                     </tbody>
#                 </table>
#             </div>
#         </div>
#     </div>
# </div>
# {% endblock %}
