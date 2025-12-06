# 🏥 Clinical Appointment Booking System

A web-based application built using **Flask** and **MySQL** to simplify appointment booking for both **patients** and **doctors**.  
The system provides an easy-to-use interface for searching doctors, viewing availability, booking appointments, and managing schedules.

---

## 🚀 Features

### 👨‍⚕️ Patient Features
- Patient Registration & Login  
- Search doctors by name, specialization, or location  
- View doctor availability (AJAX-based slot loading)  
- Book appointments  
- Reschedule or cancel appointments  
- View booking history  
- View profile  

### 🩺 Doctor Features
- Doctor Registration & Login  
- Add availability (date, time, slots)  
- View scheduled appointments  
- View doctor profile  

### 🔧 System Features
- Secure authentication using hashed passwords  
- Slot decrement/increment on booking or cancellation  
- Fully responsive and modern UI  
- Flask–MySQL backend integration  

---

## 📂 Project Folder Structure

Clinic-Appointment-Booking/
│
├── app.py
├── requirements.txt
├── .gitignore
├── .env (not included in GitHub)
│
├── static/
│ └── style.css
│
├── templates/
│ ├── base.html
│ ├── login.html
│ ├── register_patient.html
│ ├── register_doctor.html
│ ├── patient_dashboard.html
│ ├── doctor_dashboard.html
│ ├── book_appointment.html
│ ├── add_availability.html
│ ├── view_bookings_patient.html
│ └── view_appointments_doctor.html

