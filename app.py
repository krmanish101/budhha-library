from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

# ---------- Database Setup ----------
def init_db():
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect('database/library.db')
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
                    aadhar_number TEXT,
                    admission_date TEXT
                )''')

    # Books Table
    c.execute('''CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    author TEXT,
                    issued_to INTEGER,
                    issue_date TEXT,
                    return_date TEXT,
                    FOREIGN KEY(issued_to) REFERENCES students(id)
                )''')

    # Fees Table
    c.execute('''CREATE TABLE IF NOT EXISTS fees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    month TEXT,
                    amount REAL,
                    date_paid TEXT,
                    FOREIGN KEY(student_id) REFERENCES students(id)
                )''')

    conn.commit()
    conn.close()

init_db()

# ---------- DASHBOARD ----------
@app.route('/')
def index():
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM students")
    total_students = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM books")
    total_books = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM books WHERE issued_to IS NOT NULL")
    issued_books = c.fetchone()[0]

    c.execute("SELECT SUM(amount) FROM fees")
    total_fees = c.fetchone()[0] or 0

    conn.close()
    return render_template('dashboard.html',
                           total_students=total_students,
                           total_books=total_books,
                           issued_books=issued_books,
                           total_fees=total_fees)

# ---------- STUDENTS ----------
@app.route('/students')
def students():
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("SELECT * FROM students ORDER BY id DESC")
    students = c.fetchall()
    conn.close()
    return render_template('students.html', students=students)

@app.route('/add_student', methods=['POST'])
def add_student():
    data = (
        request.form['name'],
        request.form['father'],
        request.form['phone'],
        request.form['address'],
        request.form['shift'],
        request.form['sheet_no'],
        request.form['aadhar_number'],
        datetime.now().strftime("%Y-%m-%d")
    )
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("""INSERT INTO students 
        (name, father, phone, address, shift, sheet_no, aadhar_number, admission_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", data)
    conn.commit()
    conn.close()
    return redirect(url_for('students'))

@app.route('/edit_student/<int:id>', methods=['POST'])
def edit_student(id):
    data = (
        request.form['name'],
        request.form['father'],
        request.form['phone'],
        request.form['address'],
        request.form['shift'],
        request.form['sheet_no'],
        request.form['aadhar_number'],
        id
    )
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("""UPDATE students SET name=?, father=?, phone=?, address=?, shift=?, 
                 sheet_no=?, aadhar_number=? WHERE id=?""", data)
    conn.commit()
    conn.close()
    return redirect(url_for('students'))

@app.route('/delete_student/<int:id>', methods=['POST'])
def delete_student(id):
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('students'))

# ---------- BOOKS ROUTES ----------
@app.route('/books')
def books():
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("""SELECT b.id, b.title, b.author, s.name, b.issue_date, b.return_date 
                 FROM books b 
                 LEFT JOIN students s ON b.issued_to = s.id""")
    books = c.fetchall()
    conn.close()
    return render_template('books.html', books=books)

@app.route('/add_book', methods=['POST'])
def add_book():
    title = request.form['title']
    author = request.form['author']
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("INSERT INTO books (title, author) VALUES (?, ?)", (title, author))
    conn.commit()
    conn.close()
    return redirect(url_for('books'))

@app.route('/edit_book/<int:id>', methods=['POST'])
def edit_book(id):
    title = request.form['title']
    author = request.form['author']
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("UPDATE books SET title=?, author=? WHERE id=?", (title, author, id))
    conn.commit()
    conn.close()
    return redirect(url_for('books'))

@app.route('/delete_book/<int:id>', methods=['POST'])
def delete_book(id):
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("DELETE FROM books WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('books'))

@app.route('/issue_book', methods=['POST'])
def issue_book():
    book_id = request.form['book_id']
    student_id = request.form['student_id']
    issue_date = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("UPDATE books SET issued_to=?, issue_date=?, return_date=NULL WHERE id=?", 
              (student_id, issue_date, book_id))
    conn.commit()
    conn.close()
    return redirect(url_for('books'))

@app.route('/return_book/<int:id>', methods=['POST'])
def return_book(id):
    return_date = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("UPDATE books SET issued_to=NULL, return_date=? WHERE id=?", (return_date, id))
    conn.commit()
    conn.close()
    return redirect(url_for('books'))


# ---------- FEES ----------
@app.route('/fees')
def fees():
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("""SELECT fees.id, students.name, fees.month, fees.amount, fees.date_paid 
                 FROM fees JOIN students ON fees.student_id = students.id
                 ORDER BY fees.date_paid DESC""")
    fees = c.fetchall()
    c.execute("SELECT id, name FROM students")
    students = c.fetchall()
    conn.close()
    return render_template('fees.html', fees=fees, students=students)

@app.route('/add_fee', methods=['POST'])
def add_fee():
    data = (
        request.form['student_id'],
        request.form['month'],
        request.form['amount'],
        datetime.now().strftime("%Y-%m-%d")
    )
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("INSERT INTO fees (student_id, month, amount, date_paid) VALUES (?, ?, ?, ?)", data)
    conn.commit()
    conn.close()
    return redirect(url_for('fees'))

@app.route('/delete_fee/<int:id>', methods=['POST'])
def delete_fee(id):
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("DELETE FROM fees WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('fees'))

# ---------- REPORTS ----------
@app.route('/reports')
def reports():
    conn = sqlite3.connect('database/library.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM students")
    total_students = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM books")
    total_books = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM books WHERE issued_to IS NOT NULL")
    issued_books = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM fees")
    total_fees = c.fetchone()[0] or 0
    conn.close()
    return render_template('reports.html',
                           total_students=total_students,
                           total_books=total_books,
                           issued_books=issued_books,
                           total_fees=total_fees)

if __name__ == '__main__':
    app.run(debug=True)
