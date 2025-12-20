from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import re
import sqlite3
import smtplib
from email.message import EmailMessage
import random
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "123"

# ---------------- Database Initialization ----------------
def init_db():
    con = sqlite3.connect("test.db")
    cur = con.cursor()
    
    cur.execute('''CREATE TABLE IF NOT EXISTS emptbl(
                    email TEXT PRIMARY KEY,
                    password TEXT,
                    otp TEXT,
                    otpex DATETIME,
                    role TEXT,
                    name TEXT,
                    mobile TEXT,
                    empcode TEXT
                )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS empworkers(
                name TEXT,
                empcode TEXT,
                role TEXT,
                gender TEXT,
                doj DATE,
                bldgrp TEXT,
                supervisor TEXT
                )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS supervisors (
               empcode TEXT PRIMARY KEY,
               name TEXT,
               email TEXT,
               mobile TEXT,
               role TEXT DEFAULT 'supervisor'
                )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS supworkers(
                name TEXT,
                empcode TEXT,
                role TEXT,
                gender TEXT,
                doj DATE,
                bldgrp TEXT
                )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS leave_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empcode TEXT,
                supervisor_empcode TEXT,
                leave_from DATE,
                leave_to DATE,
                reason TEXT,
                status TEXT DEFAULT 'Pending',
                email_sent INTEGER DEFAULT 0
                )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS shift_schedule (
        supervisor_empcode TEXT,
        shift_name TEXT,
        start_time TEXT,
        end_time TEXT,
        week_start DATE,
        PRIMARY KEY (supervisor_empcode, week_start)
    )''')
    con.commit()
    con.close()

# ---------------- Send Email ----------------
def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = "dhanalakshmib772@gmail.com"
    msg['To'] = to_email

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login("dhanalakshmib772@gmail.com", "nfujxqwazwliawuf")  # App password
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print("Email sending failed:", e)
        return False

# ---------------- Routes ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/create", methods=["POST", "GET"])
def create():
    if request.method == "POST":
        try:
            name = request.form['name']
            role = request.form['role'].lower()
            email = request.form['email']
            password = request.form['confirmPassword']
            num = request.form['number']
            empid = request.form['empid']

            if len(password) < 10 or not re.search("[A-Z]", password) or not re.search("[a-z]", password) or not re.search("[!@#$%^&*(),.?]", password):
                flash("Password must have 10+ chars, uppercase, lowercase, and special char.", "danger")
                return redirect(url_for("create"))

            con = sqlite3.connect("test.db")
            cur = con.cursor()
            cur.execute('INSERT INTO emptbl(email, password, otp, otpex, role, name, mobile, empcode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (email, password, '', '', role, name, num, empid))
            con.commit()
            con.close()
            flash("Account created successfully!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            print(e)
            flash("Error creating account. Email might already exist.", "danger")
            return redirect(url_for("create"))
    return render_template("create.html")

@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        role = request.form['role'].lower()
        email = request.form['email']
        password = request.form['password']

        con = sqlite3.connect("test.db")
        cur = con.cursor()
        cur.execute("SELECT * FROM emptbl WHERE role=? AND email=? AND password=?", (role, email, password))
        row = cur.fetchone()
        con.close()

        if row:
            session['empid'] = row[7]
            session['name'] = row[5]
            session['role'] = row[4]
            return redirect(url_for("check"))
        else:
            flash("Invalid username or password.", "danger")
            return render_template("index.html")
    return render_template("index.html")

@app.route("/check")
def check():
    if 'name' in session and 'role' in session:
        role = session['role']
        if role == "employee":
            return redirect(url_for("emp"))
        elif role == "supervisor":
            return redirect(url_for("supervisor"))
        elif role == "hr":
            return redirect(url_for("hr"))
        else:
            flash("Invalid role. Please log in again.", "danger")
            return redirect(url_for("index"))
    else:
        flash("Session expired. Please log in again.", "warning")
        return redirect(url_for("index"))

@app.route("/supervisor", methods=["GET", "POST"])
def supervisor():
    # 🛑 Access control
    if 'empid' not in session or session.get('role') != 'supervisor':
        flash("Access denied", "danger")
        return redirect(url_for("index"))

    empid = session['empid']
    sup_name = session.get('name', 'Supervisor')
    con = sqlite3.connect("test.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # ------------------------ POST: Approve / Reject ------------------------
    if request.method == "POST":
        leave_id = request.form.get("leave_id")
        action = request.form.get("action")  # 'approve' or 'reject'

        if leave_id and action:
            action = action.strip().lower()
            status = "Approved" if action == "approve" else "Rejected"

            cur.execute("UPDATE leave_requests SET status=? WHERE id=?", (status, leave_id))
            con.commit()

            # ✅ Get employee details for email
            cur.execute("""
    SELECT ew.name, ew.empcode, et.email, lr.leave_from, lr.leave_to
    FROM leave_requests lr
    JOIN empworkers ew ON lr.empcode = ew.empcode
    JOIN emptbl et ON ew.empcode = et.empcode
    WHERE lr.id=?
""", (leave_id,))

            emp = cur.fetchone()

            if emp:
                emp_name, emp_code, emp_email, lf, lt = emp

                subject = f"Your Leave Request has been {status}"
                body = f"""
Dear {emp_name},

Your leave request from {lf} to {lt} has been {status.lower()} by your supervisor {sup_name}.

Employee ID: {emp_code}

Regards,
HR Department
"""
                email_ok = send_email(emp_email, subject, body)
                if email_ok:
                    flash(f"Leave {status} and email sent to {emp_name}.", "success")
                else:
                    flash(f"Leave {status}, but email could not be sent to {emp_name}.", "warning")
            else:
                flash("Employee not found for this leave request.", "danger")

    # ------------------------ GET: Dashboard Data ------------------------

    # ✅ 1️⃣ Total team members under this supervisor
    cur.execute("SELECT COUNT(*) FROM empworkers WHERE supervisor=?", (sup_name,))
    total_team = cur.fetchone()[0]

    # ✅ 2️⃣ Pending approvals for this supervisor
    cur.execute("""
        SELECT COUNT(*) FROM leave_requests
        WHERE supervisor_empcode=? AND status='Pending'
    """, (empid,))
    pending_approvals = cur.fetchone()[0]

    # ✅ 3️⃣ Employees on leave today
    today = datetime.now().date()
    cur.execute("""
        SELECT COUNT(*) FROM leave_requests
        WHERE supervisor_empcode=? AND status='Approved'
        AND date(?) BETWEEN date(leave_from) AND date(leave_to)
    """, (empid, today))
    on_leave_today = cur.fetchone()[0]

    # ✅ List of all leave requests (for table)
    cur.execute("""
        SELECT lr.id, e.name, e.empcode, lr.leave_from, lr.leave_to, lr.reason, lr.status
        FROM leave_requests lr
        JOIN empworkers e ON lr.empcode = e.empcode
        WHERE lr.supervisor_empcode=?
        ORDER BY lr.leave_from DESC
    """, (empid,))
    leaves = cur.fetchall()

    con.close()

    return render_template(
        "supervisor.html",
        name=sup_name,
        leaves=leaves,
        total_team=total_team,
        pending_approvals=pending_approvals,
        on_leave_today=on_leave_today
    )

@app.route("/leave_action/<action>/<int:leave_id>")
def leave_action(action, leave_id):
    con = sqlite3.connect("test.db")
    cur = con.cursor()
    status = "Approved" if action.lower() == "approve" else "Rejected"
    cur.execute("UPDATE leave_requests SET status=? WHERE id=?", (status, leave_id))
    con.commit()
    con.close()
    flash(f"Leave {status} successfully!", "success")
    return redirect(url_for("supervisor"))

@app.route("/emp")
def emp():
    return render_template("emp.html", name=session.get('name', 'User'))

@app.route("/hr")
def hr():
    con = sqlite3.connect("test.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # ✅ Fetch all employees
    cur.execute("SELECT empcode, name, role, supervisor FROM empworkers")
    empworkers = cur.fetchall()

    # ✅ Fetch all supervisors
    cur.execute("SELECT empcode, name, role FROM supworkers")
    supworkers = cur.fetchall()

    # ✅ Count totals
    total_employees = len(empworkers)
    total_supervisors = len(supworkers)

    # ✅ Optional: Count employees on leave (if leaves table exists)
    try:
        cur.execute("SELECT COUNT(DISTINCT empcode) FROM leaves WHERE status IN ('Approved', 'Pending')")
        employees_on_leave = cur.fetchone()[0]
    except:
        employees_on_leave = 0

    con.close()

    # ✅ Pass all to template
    return render_template(
        "hr.html",
        name=session.get('name', 'HR User'),
        total=total_employees,
        supervisors=total_supervisors,
        leaves=employees_on_leave,
        empworkers=empworkers,
        supworkers=supworkers
    )

@app.route("/leaverequest", methods=["POST", "GET"])
def leaverequest():
    empid = session.get('empid')
    if not empid:
        flash("Please log in to submit leave request.", "danger")
        return redirect(url_for("index"))

    if request.method == 'POST':
        leave_from = request.form['from']
        leave_to = request.form['to']
        reason = request.form['reason']

        con = sqlite3.connect("test.db")
        cur = con.cursor()

        # 1️⃣ Fetch employee details including supervisor code and email
        cur.execute("SELECT supervisor, name FROM empworkers WHERE empcode = ?", (empid,))
        emp_data = cur.fetchone()

        if not emp_data:
            flash("Employee not found.", "danger")
            con.close()
            return redirect(url_for("leaverequest"))

        supervisor_code, emp_name = emp_data

        # 2️⃣ Fetch supervisor email and name
        cur.execute("SELECT name, email FROM emptbl WHERE  role ='supervisor' AND empcode = ?", (supervisor_code,))
        sup_data = cur.fetchone()

        if not sup_data:
            # Save leave anyway
            cur.execute("""
                INSERT INTO leave_requests (empcode, supervisor_empcode, leave_from, leave_to, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (empid, supervisor_code if supervisor_code else None, leave_from, leave_to, reason))
            con.commit()
            con.close()
            flash("Leave request saved but supervisor not assigned. Please contact HR.", "warning")
            return redirect(url_for("emp"))

        sup_name, supervisor_email = sup_data

        # 3️⃣ Save leave request
        cur.execute("""
            INSERT INTO leave_requests (empcode, supervisor_empcode, leave_from, leave_to, reason, status, email_sent)
            VALUES (?, ?, ?, ?, ?, 'Pending', 0)
        """, (empid, supervisor_code, leave_from, leave_to, reason))
        leave_id = cur.lastrowid
        con.commit()

        # 4️⃣ Send email using fixed HR/company Gmail
        email_ok = False
        try:
            msg = EmailMessage()
            msg['From'] = "dhanalakshmib772@gmail.com"
            msg['To'] = supervisor_email
            msg['Subject'] = f"Leave Request from {emp_name} ({empid})"
            msg.set_content(f"""
Dear {sup_name},

Your team member {emp_name} (Employee ID: {empid}) has submitted a leave request.

Leave Dates: {leave_from} to {leave_to}
Reason: {reason}


Please review this request.

Regards,
HR Portal
""")
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            server.login("dhanalakshmib772@gmail.com", "nfujxqwazwliawuf")  # Gmail App Password
            server.send_message(msg)
            server.quit()
            email_ok = True

        except Exception as e:
            print("Error sending email:", e)
            email_ok = False

        # 5️⃣ Update email_sent flag
        try:
            cur.execute("UPDATE leave_requests SET email_sent=? WHERE id=?", (1 if email_ok else 0, leave_id))
            con.commit()
        except Exception as e:
            print("Error updating email_sent:", e)
        finally:
            con.close()

        if email_ok:
            flash("Leave request submitted and email sent to supervisor.", "success")
        else:
            flash("Leave request saved but email could not be sent. Supervisor will be notified later.", "warning")

        return redirect(url_for("emp"))

    # GET request
    return render_template("leaverequest.html", name=session.get('name'))

@app.route("/my_leaves")
def my_leaves():
    if 'empid' not in session:
        flash("Please log in to view your leaves.", "danger")
        return redirect(url_for("index"))

    empid = session['empid']
    con = sqlite3.connect("test.db")
    cur = con.cursor()
    cur.execute("""
        SELECT leave_from, leave_to, reason, status
        FROM leave_requests
        WHERE empcode = ?
        ORDER BY leave_from DESC
    """, (empid,))
    leaves = cur.fetchall()
    con.close()
    return render_template("my_leaves.html", leaves=leaves)
@app.route("/employee_calendar/<empid>")
def employee_calendar(empid):
    con = sqlite3.connect("test.db")
    cur = con.cursor()

    # ✅ Fetch all approved leave periods for this employee
    cur.execute("""
        SELECT leave_from, leave_to 
        FROM leave_requests 
        WHERE empcode = ? AND status = 'Approved'
    """, (empid,))
    rows = cur.fetchall()
    con.close()

    leave_days = []

    for lf, lt in rows:
        try:
            start_date = datetime.strptime(lf, "%Y-%m-%d")
            end_date = datetime.strptime(lt, "%Y-%m-%d")
            current = start_date

            # ✅ Add *every leave date* as (year, month, day)
            while current <= end_date:
                leave_days.append({
                    "year": current.year,
                    "month": current.month,
                    "day": current.day
                })
                current += timedelta(days=1)
        except Exception as e:
            print("Date parse error:", e)

    return render_template("att.html", leave_days=leave_days)

@app.route("/back")
def back():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("index"))

# ---------------- Forgot Password + OTP ----------------
@app.route("/forgot_reset", methods=["POST", "GET"])
def forgot_reset():
    if request.method == "POST":
        email = request.form["email"]
        con = sqlite3.connect("test.db")
        cur = con.cursor()
        cur.execute("SELECT email FROM emptbl WHERE email=?", (email,))
        user = cur.fetchone()

        if not user:
            flash("Email not found!", "danger")
            return redirect(url_for("forgot_reset"))

        otp = str(random.randint(100000, 999999))
        expiry = datetime.now() + timedelta(minutes=5)

        cur.execute("UPDATE emptbl SET otp=?, otpex=? WHERE email=?", (otp, expiry, email))
        con.commit()
        con.close()

        if send_email(email, "Password Reset OTP", f"Your OTP is {otp}. Valid for 5 minutes."):
            session["reset_email"] = email
            flash("OTP sent successfully! Check your email.", "info")
            return redirect(url_for("verify_otp"))
        else:
            flash("Failed to send email.", "danger")
            return redirect(url_for("forgot_reset"))
    return render_template("forgot_reset.html")

@app.route("/verify_otp", methods=["POST", "GET"])
def verify_otp():
    if request.method == "POST":
        email = session.get("reset_email")
        otp_entered = request.form["otp"]
        con = sqlite3.connect("test.db")
        cur = con.cursor()
        cur.execute("SELECT otp, otpex FROM emptbl WHERE email=?", (email,))
        data = cur.fetchone()
        con.close()

        if data and data[0] == otp_entered and datetime.now() < datetime.fromisoformat(data[1]):
            flash("OTP verified! Reset your password.", "success")
            return redirect(url_for("reset_password"))
        else:
            flash("Invalid or expired OTP.", "danger")
            return redirect(url_for("verify_otp"))
    return render_template("verify_otp.html")

@app.route("/reset_password", methods=["POST", "GET"])
def reset_password():
    if request.method == "POST":
        email = session.get("reset_email")
        new_password = request.form["new_password"]

        if len(new_password) < 10:
            flash("Password must be at least 10 characters long.", "danger")
            return redirect(url_for("reset_password"))

        con = sqlite3.connect("test.db")
        cur = con.cursor()
        cur.execute("UPDATE emptbl SET password=?, otp='', otpex='' WHERE email=?", (new_password, email))
        con.commit()
        con.close()

        session.pop("reset_email", None)
        flash("Password reset successful! Please log in.", "success")
        return redirect(url_for("index"))
    return render_template("reset_password.html")
@app.route("/mydetails")
def mydetails():
    if 'empid' not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for("index"))

    empid = session['empid']
    con = sqlite3.connect("test.db")
    cur = con.cursor()
    cur.execute("SELECT name, email, mobile, empcode, role FROM emptbl WHERE empcode=?", (empid,))
    data = cur.fetchone()
    con.close()

    return render_template("mydetails.html", data=data)
@app.route("/contact")
def contact():
    return render_template("contact.html")
@app.route("/about")
def about():
    return render_template("about.html")
# ---------------- Add Employee ----------------
@app.route("/addemp", methods=["GET", "POST"])
def addemp():
    con = sqlite3.connect("test.db")
    cur = con.cursor()

    # ✅ Fetch both empid and name
    cur.execute("SELECT empcode, name FROM supworkers")
    supervisors = cur.fetchall()

    if request.method == "POST":
        name = request.form['name']
        empcode = request.form['empid']
        role = request.form['designation']
        gender = request.form['gender']
        doj = request.form['doj']
        blood = request.form['bldgrp']
        supervisor = request.form['supervisor']

        cur.execute(
            "INSERT INTO empworkers (name, empcode, role, gender, doj, bldgrp, supervisor) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, empcode, role, gender, doj, blood, supervisor)
        )
        con.commit()
        con.close()
        flash("Employee added successfully!", "success")
        return redirect(url_for("addemp"))

    con.close()
    return render_template("addemp.html", supervisors=supervisors)
# ---------------- Add Supervisor ----------------
@app.route("/addsup", methods=["POST", "GET"])
def addsup():
    if request.method == 'POST':
        name = request.form['name']
        empids = request.form['empid']
        role = request.form['designation']
        doj = request.form['doj']
        gender = request.form['gender']
        bldgrp = request.form['bldgrp']

        try:
            con = sqlite3.connect("test.db", timeout=10)  # ⏳ wait up to 10s for lock
            cur = con.cursor()

            cur.execute("""
                INSERT INTO supworkers (name, empcode, role, gender, doj, bldgrp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, empids, role, gender, doj, bldgrp))

            con.commit()
            flash("Supervisor added successfully!", "success")

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                flash("⚠ Database is busy. Try again after a few seconds.", "warning")
            else:
                flash(f"Error adding supervisor: {e}", "danger")

        finally:
            con.close()  # ✅ always close the connection

        return redirect(url_for("hr"))
    else:
        return render_template("addsup.html")
# ---------------- Delete Supervisor ----------------
@app.route("/deletesup", methods=["GET", "POST"])
def deletesup():
    if request.method == "POST":
        empid = request.form['empid']

        con = sqlite3.connect("test.db")
        cur = con.cursor()

        try:
            cur.execute("DELETE FROM supworkers WHERE empcode=?", (empid,))
            con.commit()
            flash(f"Supervisor {empid} deleted successfully!", "success")
        except Exception as e:
            flash(f"Error deleting supervisor: {e}", "danger")
        finally:
            con.close()

        return redirect(url_for('deletesup'))

    return render_template('deletesup.html')
# ---------------- Delete Employee ----------------
@app.route("/deleteemp", methods=["GET", "POST"])
def deleteemp():
    if request.method == "POST":
        empid = request.form["empid"]

        con = sqlite3.connect("test.db")
        cur = con.cursor()
        try:
            cur.execute("DELETE FROM empworkers WHERE empcode=?", (empid,))
            con.commit()
            flash(f"✅ Employee {empid} deleted successfully!", "success")
        except Exception as e:
            flash(f"❌ Error deleting employee: {e}", "danger")
        finally:
            con.close()

        return redirect(url_for("deleteemp"))

    return render_template("deleteemp.html")

@app.route("/myteam")
def myteam():
    # ✅ Ensure supervisor is logged in
    if 'empid' not in session or session.get('role') != 'supervisor':
        flash("Access denied! Only supervisors can view this page.", "danger")
        return redirect(url_for("index"))

    supervisor_empcode = session['empid']
    con = sqlite3.connect("test.db")
    cur = con.cursor()

    # ✅ Fetch team members under this supervisor
    cur.execute("""
        SELECT w.empcode, w.name, w.role, e.email
        FROM empworkers w
        LEFT JOIN emptbl e ON w.empcode = e.empcode
        WHERE w.supervisor = ?
    """, (supervisor_empcode,))

    rows = cur.fetchall()
    con.close()

    # ✅ Convert to dicts (Flask template friendly)
    team_members = [
        {"empcode": r[0], "name": r[1], "role": r[2], "email": r[3]} for r in rows
    ]

    return render_template("myteam.html", team_members=team_members)

# ---------------- Shift Definitions ----------------
SHIFTS = [
    ("Shift 1", "07:00", "15:00"),   # Morning
    ("Shift 2", "15:30", "00:30"),   # Evening
    ("Shift 3", "01:00", "07:00")    # Night
]

# ---------------- Shift Rotation Logic ----------------
def _rotate_shifts_logic():
    con = sqlite3.connect("test.db")
    cur = con.cursor()

    # 1️⃣ Get all supervisors in fixed order
    cur.execute("SELECT empcode FROM supworkers ORDER BY empcode")
    supervisors = [row[0] for row in cur.fetchall()]
    n = len(supervisors)

    if n == 0:
        print("⚠️ No supervisors found.")
        con.close()
        return False

    # 2️⃣ Calculate next week start (Monday)
    today = datetime.now().date()
    next_week_start = today + timedelta(days=(7 - today.weekday()))

    # 3️⃣ Get last week's shifts
    cur.execute("""
        SELECT supervisor_empcode, shift_name 
        FROM shift_schedule 
        WHERE week_start = (SELECT MAX(week_start) FROM shift_schedule)
    """)
    last_week = cur.fetchall()

    if not last_week:
        # Initial assignment (different shifts for each)
        for i, sup in enumerate(supervisors):
            shift = SHIFTS[i % len(SHIFTS)]
            cur.execute("""
                INSERT OR REPLACE INTO shift_schedule 
                (supervisor_empcode, shift_name, start_time, end_time, week_start)
                VALUES (?, ?, ?, ?, ?)
            """, (sup, shift[0], shift[1], shift[2], next_week_start))
    else:
        # Create mapping of supervisor → last shift index
        last_shifts = {sup: sname for sup, sname in last_week}

        # Rotate each supervisor's shift
        for i, sup in enumerate(supervisors):
            last_name = last_shifts.get(sup, SHIFTS[i % 3][0])
            last_index = next((idx for idx, s in enumerate(SHIFTS) if s[0] == last_name), 0)
            next_index = (last_index + 1) % len(SHIFTS)
            shift = SHIFTS[next_index]

            cur.execute("""
                INSERT OR REPLACE INTO shift_schedule 
                (supervisor_empcode, shift_name, start_time, end_time, week_start)
                VALUES (?, ?, ?, ?, ?)
            """, (sup, shift[0], shift[1], shift[2], next_week_start))

    con.commit()
    con.close()
    print("✅ Shift rotation completed for week starting", next_week_start)
    return True


@app.route("/rotate_shifts_now")
def rotate_shifts_now():
    ok = _rotate_shifts_logic()
    if ok:
        flash("✅ Shift rotation done for next week!", "success")
    else:
        flash("⚠️ No supervisors found to rotate.", "warning")
    return redirect(url_for("view_shifts"))


@app.route("/shifts")
def view_shifts():
    con = sqlite3.connect("test.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("""
        SELECT s.supervisor_empcode, w.name, s.shift_name, s.start_time, s.end_time, s.week_start
        FROM shift_schedule s
        LEFT JOIN supworkers w ON s.supervisor_empcode = w.empcode
        ORDER BY s.week_start DESC, s.supervisor_empcode
    """)
    rows = cur.fetchall()
    con.close()
    return render_template("shifts.html", shifts=rows)
@app.route("/my_shift")
def my_shift():
    if 'empid' not in session or session.get('role') != 'supervisor':
        flash("Access denied!", "danger")
        return redirect(url_for("index"))

    supervisor_empcode = session['empid']

    con = sqlite3.connect("test.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # ✅ Fetch the latest shift for the current supervisor
    cur.execute("""
        SELECT shift_name, start_time, end_time, week_start
        FROM shift_schedule
        WHERE supervisor_empcode = ?
        ORDER BY week_start DESC
        LIMIT 1
    """, (supervisor_empcode,))
    shift = cur.fetchone()
    con.close()

    # ✅ Calculate week range
    if shift:
        week_start = datetime.strptime(shift['week_start'], "%Y-%m-%d")
        week_end = week_start + timedelta(days=6)
        return render_template(
            "my_shift.html",
            shift_name=shift['shift_name'],
            start_time=shift['start_time'],
            end_time=shift['end_time'],
            week_start=week_start.strftime("%a %b %d %Y"),
            week_end=week_end.strftime("%a %b %d %Y")
        )
    else:
        flash("No shift data found for you yet.", "warning")
        return redirect(url_for("supervisor"))
@app.route("/view_employees")
def view_employees():
    con = sqlite3.connect("test.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # ✅ Fetch all employees with their assigned supervisor
    cur.execute("""
        SELECT 
            e.empcode AS empid,
            e.name AS emp_name,
            e.role,
            e.gender,
            e.doj,
            e.bldgrp,
            e.supervisor AS supervisor_name
        FROM empworkers e
        ORDER BY e.empcode ASC
    """)

    employees = cur.fetchall()
    con.close()

    return render_template("employees.html", employees=employees)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
