# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Optional Twilio import for SMS (install twilio) - shown later
# from twilio.rest import Client

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "devsecret123")

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST","localhost"),
        user=os.getenv("DB_USER","root"),
        password=os.getenv("DB_PASS","Gangadhar@13"),
        database=os.getenv("DB_NAME","clinicdb")
    )

# ---------- Helper: send email ----------
def send_email(to_email, subject, html_body):
    # Uses SMTP. Configure below (GMAIL example)
    smtp_host = os.getenv("SMTP_HOST","smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT",587))
    smtp_user = os.getenv("SMTP_USER")  # your email
    smtp_pass = os.getenv("SMTP_PASS")  # app password or SMTP password

    if not smtp_user or not smtp_pass:
        print("SMTP credentials not set; skipping email.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to_email

        part1 = MIMEText(html_body, "html")
        msg.attach(part1)

        try:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        except Exception as e:
            print("SMTP connection failed:", e)
            return False

        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("Email send failed:", e)
        return False

# ---------- Helper: send SMS (Twilio) - optional ----------
def send_sms(to_number, message):
    # Disable SMS completely
    print("SMS sending disabled — no Twilio credentials.")
    return False


# ---------- Routes ----------
@app.route("/")
def index():
    if session.get("user_type") == "patient":
        return redirect(url_for("patient_dashboard"))
    if session.get("user_type") == "doctor":
        return redirect(url_for("doctor_dashboard"))
    return render_template("login.html")

# ---------- Registration ----------
@app.route("/register/patient", methods=["GET","POST"])
def register_patient():
    if request.method == "POST":
        name = request.form["name"].strip()
        age = request.form.get("age") or None
        mobile = request.form["mobile"].strip()
        email = request.form["email"].strip()
        pwd = request.form["password"]
        cpwd = request.form["confirm_password"]
        if pwd != cpwd:
            flash("Passwords do not match","danger")
            return redirect(url_for("register_patient"))
        hashed = generate_password_hash(pwd)
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO patients (name, age, mobile, email, password_hash) VALUES (%s,%s,%s,%s,%s)",
                        (name, age if age else None, mobile, email, hashed))
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except mysql.connector.errors.IntegrityError as e:
            flash("Email or mobile already registered.", "danger")
            return redirect(url_for("register_patient"))
        finally:
            cur.close(); conn.close()
    return render_template("register_patient.html")

@app.route("/register/doctor", methods=["GET","POST"])
def register_doctor():
    if request.method == "POST":
        name = request.form["name"].strip()
        spec = request.form["specialization"].strip()
        clinic = request.form["clinic_location"].strip()
        email = request.form["email"].strip()
        mobile = request.form["mobile"].strip()
        pwd = request.form["password"]
        cpwd = request.form["confirm_password"]
        if pwd != cpwd:
            flash("Passwords do not match","danger")
            return redirect(url_for("register_doctor"))
        hashed = generate_password_hash(pwd)
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""INSERT INTO doctors
                           (name, specialization, clinic_location, email, mobile, password_hash)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (name, spec, clinic, email, mobile, hashed))
            conn.commit()
            flash("Doctor registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except mysql.connector.errors.IntegrityError as e:
            flash("Email or mobile already registered.", "danger")
            return redirect(url_for("register_doctor"))
        finally:
            cur.close(); conn.close()
    return render_template("register_doctor.html")

# ---------- Login (email or mobile) ----------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        identifier = request.form["identifier"].strip()  # email or mobile
        password = request.form["password"]
        # search patients first
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        user = None
        try:
            cur.execute("SELECT * FROM patients WHERE email=%s OR mobile=%s", (identifier, identifier))
            user = cur.fetchone()
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["user_type"] = "patient"
                session["user_name"] = user["name"]
                flash("Logged in as patient", "success")
                return redirect(url_for("patient_dashboard"))
            # try doctor
            cur.execute("SELECT * FROM doctors WHERE email=%s OR mobile=%s", (identifier, identifier))
            doc = cur.fetchone()
            if doc and check_password_hash(doc["password_hash"], password):
                session.clear()
                session["user_id"] = doc["id"]
                session["user_type"] = "doctor"
                session["user_name"] = doc["name"]
                flash("Logged in as doctor", "success")
                return redirect(url_for("doctor_dashboard"))
            flash("Invalid credentials", "danger")
            return redirect(url_for("login"))
        finally:
            cur.close(); conn.close()
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("login"))

# ---------- Patient dashboard ----------
@app.route("/patient")
def patient_dashboard():
    if session.get("user_type") != "patient":
        return redirect(url_for("login"))
    return render_template("patient_dashboard.html", name=session.get("user_name"))

# Book appointment: list doctors + search + show availabilities
@app.route("/patient/book", methods=["GET","POST"])
def book_appointment():
    if session.get("user_type") != "patient":
        return redirect(url_for("login"))
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        q = request.args.get("q","").strip()
        if q:
            cur.execute("""SELECT d.*, 
                           (SELECT COUNT(*) FROM availabilities a WHERE a.doctor_id=d.id AND a.date >= CURDATE()) as upcoming_slots
                           FROM doctors d
                           WHERE d.name LIKE %s OR d.specialization LIKE %s OR d.clinic_location LIKE %s
                           """, (f"%{q}%","%"+q+"%","%"+q+"%"))
        else:
            cur.execute("""SELECT d.*,
                           (SELECT COUNT(*) FROM availabilities a WHERE a.doctor_id=d.id AND a.date >= CURDATE()) as upcoming_slots
                           FROM doctors d""")
        doctors = cur.fetchall()
        # If booking POST
        if request.method == "POST" or request.form.get("doctor_id"):
            # for booking we expect a JSON POST via form submission: doctor_id,date,time
            pass
        return render_template("book_appointment.html", doctors=doctors, q=q)
    finally:
        cur.close(); conn.close()

# Endpoint to fetch availabilities for a doctor (AJAX)
@app.route("/doctor/<int:doctor_id>/availabilities")
def get_availabilities(doctor_id):
    from datetime import timedelta

    def convert_time(t):
        # Case 1: timedelta (e.g., 1:00:00)
        if isinstance(t, timedelta):
            total_seconds = int(t.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"

        # Case 2: datetime.time with strftime
        if hasattr(t, "strftime"):
            return t.strftime("%H:%M")

        # Case 3: Already a string
        return str(t)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT id, date, start_time, end_time, slots 
               FROM availabilities
               WHERE doctor_id=%s AND date >= CURDATE()
               ORDER BY date, start_time""",
            (doctor_id,)
        )
        rows = cur.fetchall()

        # Convert date and time safely
        for r in rows:
            r["date"] = r["date"].strftime("%Y-%m-%d")
            r["start_time"] = convert_time(r["start_time"])
            r["end_time"] = convert_time(r["end_time"])

        return jsonify(rows)

    finally:
        cur.close()
        conn.close()


# Booking action (patient posts)
@app.route("/patient/book_action", methods=["POST"])
def patient_book_action():
    if session.get("user_type") != "patient":
        return redirect(url_for("login"))
    doctor_id = int(request.form["doctor_id"])
    date_str = request.form["date"]
    time_str = request.form["time"]
    patient_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # check availability slot exists and has slots left
        cur.execute("""SELECT id, slots FROM availabilities
                       WHERE doctor_id=%s AND date=%s AND start_time=%s FOR UPDATE""",
                    (doctor_id, date_str, time_str))
        av = cur.fetchone()
        if not av:
            flash("Selected slot not available", "danger")
            return redirect(url_for("book_appointment"))
        avail_id, slots = av
        if slots <= 0:
            flash("No slots left for that time", "danger")
            return redirect(url_for("book_appointment"))
        # decrement slot
        cur.execute("UPDATE availabilities SET slots = slots-1 WHERE id=%s", (avail_id,))
        cur.execute("INSERT INTO appointments (patient_id, doctor_id, date, time) VALUES (%s,%s,%s,%s)",
                    (patient_id, doctor_id, date_str, time_str))
        conn.commit()
        # send alerts
        # get emails/mobiles
        cur.execute("SELECT email, mobile, name FROM patients WHERE id=%s", (patient_id,))
        p = cur.fetchone()
        cur.execute("SELECT email, mobile, name FROM doctors WHERE id=%s", (doctor_id,))
        d = cur.fetchone()
    finally:
        cur.close(); conn.close()

    patient_email, patient_mobile, patient_name = p
    doctor_email, doctor_mobile, doctor_name = d
    subj = "Appointment booked"
    html_msg = f"""
        <h3>Appointment confirmation</h3>
        <p>Hi {patient_name}, your appointment with {doctor_name} on {date_str} at {time_str} is confirmed.</p>
    """
    send_email(patient_email, subj, html_msg)
    send_email(doctor_email, "New appointment booked", f"<p>Doctor {doctor_name}, you have an appointment with {patient_name} on {date_str} at {time_str}.</p>")
    # SMS (optional)
    send_sms(patient_mobile, f"Appointment confirmed with {doctor_name} on {date_str} {time_str}")
    send_sms(doctor_mobile, f"New appointment with {patient_name} on {date_str} {time_str}")

    flash("Appointment booked and notifications sent (if configured).", "success")
    return redirect(url_for("view_bookings_patient"))

# View bookings (patient)
@app.route("/patient/bookings")
def view_bookings_patient():
    if session.get("user_type") != "patient":
        return redirect(url_for("login"))
    patient_id = session["user_id"]
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT a.*, d.name as doctor_name, d.specialization
                       FROM appointments a JOIN doctors d ON a.doctor_id=d.id
                       WHERE a.patient_id=%s ORDER BY a.date DESC, a.time DESC""", (patient_id,))
        rows = cur.fetchall()
        return render_template("view_bookings_patient.html", bookings=rows)
    finally:
        cur.close(); conn.close()

# Reschedule or cancel
@app.route("/patient/booking_action/<int:appointment_id>", methods=["POST"])
def booking_action(appointment_id):
    if session.get("user_type") != "patient":
        return redirect(url_for("login"))
    action = request.form.get("action")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM appointments WHERE id=%s", (appointment_id,))
        appt = cur.fetchone()
        if not appt:
            flash("Appointment not found", "danger")
            return redirect(url_for("view_bookings_patient"))

        if action == "cancel":
            cur.execute("UPDATE appointments SET status='cancelled' WHERE id=%s", (appointment_id,))
            conn.commit()
            # increment availability slot back (optional)
            cur.execute("""UPDATE availabilities SET slots = slots+1 WHERE doctor_id=%s AND date=%s AND start_time=%s""",
                        (appt["doctor_id"], appt["date"], appt["time"]))
            conn.commit()
            # notify
            # fetch details
            cur.execute("SELECT email,mobile,name FROM patients WHERE id=%s", (appt["patient_id"],))
            p = cur.fetchone()
            cur.execute("SELECT email,mobile,name FROM doctors WHERE id=%s", (appt["doctor_id"],))
            d = cur.fetchone()
            send_email(p["email"], "Appointment cancelled", f"<p>Your appointment on {appt['date']} {appt['time']} is cancelled.</p>")
            send_email(d["email"], "Appointment cancelled", f"<p>Appointment with {p['name']} on {appt['date']} {appt['time']} was cancelled.</p>")
            send_sms(p["mobile"], f"Your appointment on {appt['date']} {appt['time']} was cancelled.")
            send_sms(d["mobile"], f"Appointment on {appt['date']} {appt['time']} cancelled.")
            flash("Appointment cancelled and notifications sent", "info")
        elif action == "reschedule":
            new_date = request.form.get("new_date")
            new_time = request.form.get("new_time")
            # TODO: check availability exists and slot >0; for brevity assume valid
            cur.execute("UPDATE appointments SET date=%s, time=%s, status='rescheduled' WHERE id=%s", (new_date, new_time, appointment_id))
            # adjust slots: increments old availability and decrement new availability
            cur.execute("""UPDATE availabilities SET slots = slots+1 WHERE doctor_id=%s AND date=%s AND start_time=%s""",
                        (appt["doctor_id"], appt["date"], appt["time"]))
            cur.execute("""UPDATE availabilities SET slots = slots-1 WHERE doctor_id=%s AND date=%s AND start_time=%s""",
                        (appt["doctor_id"], new_date, new_time))
            conn.commit()
            # notify
            cur.execute("SELECT email,mobile,name FROM patients WHERE id=%s", (appt["patient_id"],))
            p = cur.fetchone()
            cur.execute("SELECT email,mobile,name FROM doctors WHERE id=%s", (appt["doctor_id"],))
            d = cur.fetchone()
            send_email(p["email"], "Appointment rescheduled", f"<p>Your appointment is moved to {new_date} {new_time}.</p>")
            send_email(d["email"], "Appointment rescheduled", f"<p>Appointment with {p['name']} rescheduled to {new_date} {new_time}.</p>")
            send_sms(p["mobile"], f"Appointment rescheduled to {new_date} {new_time}.")
            send_sms(d["mobile"], f"Appointment rescheduled to {new_date} {new_time}.")
            flash("Appointment rescheduled and notifications sent", "success")
    finally:
        cur.close(); conn.close()
    return redirect(url_for("view_bookings_patient"))

# Patient profile
@app.route("/patient/profile")
def patient_profile():
    if session.get("user_type") != "patient":
        return redirect(url_for("login"))
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id, name, age, email, mobile, created_at FROM patients WHERE id=%s", (session["user_id"],))
        user = cur.fetchone()
        return render_template("patient_profile.html", user=user)
    finally:
        cur.close(); conn.close()

# ---------- Doctor section ----------
@app.route("/doctor")
def doctor_dashboard():
    if session.get("user_type") != "doctor":
        return redirect(url_for("login"))
    return render_template("doctor_dashboard.html", name=session.get("user_name"))

@app.route("/doctor/add_availability", methods=["GET","POST"])
def doctor_add_availability():
    if session.get("user_type") != "doctor":
        return redirect(url_for("login"))
    if request.method == "POST":
        d_id = session["user_id"]
        date_str = request.form["date"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        slots = int(request.form.get("slots",1))
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""INSERT INTO availabilities (doctor_id, date, start_time, end_time, slots)
                           VALUES (%s,%s,%s,%s,%s)""", (d_id, date_str, start_time, end_time, slots))
            conn.commit()
            flash("Availability added", "success")
        except Exception as e:
            flash("Could not add availability", "danger")
        finally:
            cur.close(); conn.close()
        return redirect(url_for("doctor_add_availability"))
    return render_template("add_availability.html")

@app.route("/doctor/appointments")
def doctor_view_appointments():
    if session.get("user_type") != "doctor":
        return redirect(url_for("login"))
    d_id = session["user_id"]
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT a.*, p.name as patient_name, p.mobile as patient_mobile
                       FROM appointments a JOIN patients p ON a.patient_id=p.id
                       WHERE a.doctor_id=%s ORDER BY a.date DESC, a.time DESC""", (d_id,))
        rows = cur.fetchall()
        return render_template("view_appointments_doctor.html", bookings=rows)
    finally:
        cur.close(); conn.close()

@app.route("/doctor/profile")
def doctor_profile():
    if session.get("user_type") != "doctor":
        return redirect(url_for("login"))
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id, name, specialization, clinic_location, email, mobile, created_at FROM doctors WHERE id=%s", (session["user_id"],))
        doc = cur.fetchone()
        return render_template("doctor_profile.html", doctor=doc)
    finally:
        cur.close(); conn.close()

# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)
