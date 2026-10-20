
from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import os
from dotenv import load_dotenv
from functools import wraps
from datetime import date

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "college-attendance-demo-secret")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", "18192")),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "ssl_disabled": False
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def get_db_connection():
    return get_db()
 
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("You do not have permission for this page.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.route("/")
def home():
    def home():
     session.clear()
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        if password != request.form["confirm_password"]:
            return render_template(
                "register.html",
                error="Passwords do not match."
        )
        role = request.form["role"] 

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (username,)
        )

        if cursor.fetchone():
            cursor.close()
            conn.close()
            return render_template(
                "register.html",
                error="Username already exists."
            )

        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (username, password, role)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute(
            "SELECT id, username, role FROM users WHERE username=%s AND password=%s",
            (username, password)
        )
        user = cur.fetchone()
        cur.close()
        db.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT COUNT(*) AS total FROM students")
    total_students = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM attendance WHERE attendance_date=CURDATE() AND status='Present'")
    present_today = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM attendance WHERE attendance_date=CURDATE() AND status='Absent'")
    absent_today = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM attendance WHERE attendance_date=CURDATE() AND status='Late'")
    late_today = cur.fetchone()["total"]

    cur.close()
    db.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        late_today=late_today
    )

@app.route("/students")
@role_required("admin")
def students():
    db = get_db()
    cur = db.cursor(dictionary=True)
    q = request.args.get("q", "").strip()

    if q:
        like = f"%{q}%"
        cur.execute(
            """SELECT * FROM students
               WHERE student_id LIKE %s OR name LIKE %s
               OR class_name LIKE %s OR department LIKE %s
               ORDER BY id DESC""",
            (like, like, like, like)
        )
    else:
        cur.execute("SELECT * FROM students ORDER BY id DESC")

    rows = cur.fetchall()
    cur.close()
    db.close()
    return render_template("students.html", students=rows, q=q)

@app.route("/students/add", methods=["GET", "POST"])
@role_required("admin")
def add_student():
    if request.method == "POST":
        data = (
            request.form["student_id"].strip(),
            request.form["name"].strip(),
            request.form["class_name"].strip(),
            request.form["department"].strip(),
            request.form["email"].strip()
        )
        db = get_db()
        cur = db.cursor()
        try:
            cur.execute(
                """INSERT INTO students
                   (student_id, name, class_name, department, email)
                   VALUES (%s,%s,%s,%s,%s)""", data
            )
            db.commit()
            flash("Student added successfully.", "success")
        except mysql.connector.Error as e:
            db.rollback()
            flash(f"Could not add student: {e}", "danger")
        finally:
            cur.close()
            db.close()
        return redirect(url_for("students"))
    return render_template("student_form.html")

@app.route("/students/delete/<int:student_id>", methods=["POST"])
@role_required("admin")
def delete_student(student_id):
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("DELETE FROM students WHERE id=%s", (student_id,))
        db.commit()
        flash("Student deleted.", "success")
    except mysql.connector.Error as e:
        db.rollback()
        flash(f"Could not delete student: {e}", "danger")
    finally:
        cur.close()
        db.close()
    return redirect(url_for("students"))

@app.route("/subjects")
@role_required("admin")
def subjects():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM subjects ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close()
    db.close()
    return render_template("subjects.html", subjects=rows)

@app.route("/subjects/add", methods=["POST"])
@role_required("admin")
def add_subject():
    name = request.form["name"].strip()
    if name:
        db = get_db()
        cur = db.cursor()
        cur.execute("INSERT INTO subjects (name) VALUES (%s)", (name,))
        db.commit()
        cur.close()
        db.close()
        flash("Subject added.", "success")
    return redirect(url_for("subjects"))

@app.route("/attendance", methods=["GET", "POST"])
@role_required("admin", "faculty")
def attendance():
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT * FROM students ORDER BY name")
    students_list = cur.fetchall()
    cur.execute("SELECT * FROM subjects ORDER BY name")
    subjects_list = cur.fetchall()

    if request.method == "POST":
        attendance_date = request.form["attendance_date"]
        subject_id = request.form["subject_id"]

        for student in students_list:
            status = request.form.get(f"status_{student['id']}", "Absent")
            cur.execute(
                """INSERT INTO attendance
                   (student_id, subject_id, attendance_date, status)
                   VALUES (%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE status=VALUES(status)""",
                (student["id"], subject_id, attendance_date, status)
            )

        db.commit()
        cur.close()
        db.close()
        flash("Attendance saved successfully.", "success")
        return redirect(url_for("attendance"))

    cur.close()
    db.close()
    return render_template(
        "attendance.html",
        students=students_list,
        subjects=subjects_list,
        today=date.today().isoformat()
    )

@app.route("/reports")
@login_required
def reports():
    db = get_db()
    cur = db.cursor(dictionary=True)

    student_filter = request.args.get("student_id", "").strip()
    subject_filter = request.args.get("subject_id", "").strip()

    query = """
        SELECT a.attendance_date, s.student_id, s.name,
               s.class_name, sub.name AS subject, a.status
        FROM attendance a
        JOIN students s ON a.student_id=s.id
        JOIN subjects sub ON a.subject_id=sub.id
        WHERE 1=1
    """
    params = []

    if student_filter:
        query += " AND s.student_id=%s"
        params.append(student_filter)
    if subject_filter:
        query += " AND sub.id=%s"
        params.append(subject_filter)

    query += " ORDER BY a.attendance_date DESC, s.name"
    cur.execute(query, tuple(params))
    rows = cur.fetchall()

    cur.execute("SELECT * FROM students ORDER BY name")
    student_list = cur.fetchall()
    cur.execute("SELECT * FROM subjects ORDER BY name")
    subject_list = cur.fetchall()

    cur.close()
    db.close()
    return render_template(
        "reports.html",
        rows=rows,
        students=student_list,
        subjects=subject_list,
        student_filter=student_filter,
        subject_filter=subject_filter
    )

@app.route("/my-attendance")
@role_required("student")
def my_attendance():
    # Demo mapping: student1 account shows STU001.
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT a.attendance_date, sub.name AS subject, a.status
        FROM attendance a
        JOIN students s ON a.student_id=s.id
        JOIN subjects sub ON a.subject_id=sub.id
        WHERE s.student_id='STU001'
        ORDER BY a.attendance_date DESC
    """)
    rows = cur.fetchall()

    cur.execute("""
        SELECT
          COUNT(*) AS total,
          SUM(status='Present') AS present
        FROM attendance a
        JOIN students s ON a.student_id=s.id
        WHERE s.student_id='STU001'
    """)
    summary = cur.fetchone()
    cur.close()
    db.close()

    total = summary["total"] or 0
    present = summary["present"] or 0
    percentage = round((present / total) * 100, 2) if total else 0

    return render_template(
        "my_attendance.html",
        rows=rows,
        total=total,
        present=present,
        percentage=percentage
    )


if __name__ == "__main__":
    app.run(debug=True)
