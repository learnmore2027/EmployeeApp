# AttendEase - Employee Attendance System

## Stack
- **Backend:** Django 6 + Django REST Framework
- **Frontend:** HTML, CSS, JavaScript (face-api.js)
- **Database:** PostgreSQL

---

## Setup Guide

### 1. PostgreSQL Setup
PostgreSQL install karo aur ek database banao:

```sql
CREATE DATABASE employeedb;
CREATE USER postgres WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE employeedb TO postgres;
```

`backend/employeeapp/settings.py` mein apna DB password update karo.

### 2. Backend Run Karo
```bash
cd backend
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 3. Employee Register Karo (Admin Panel)
- Browser mein jao: http://127.0.0.1:8000/admin/
- Login karo superuser se
- "Users" > "Add User" > Username, Password, First Name, Last Name bharo
- Employee Profile mein Employee ID aur Department bharo
- Save karo

### 4. Face Register Karo
- `frontend/register_face.html` kholo browser mein
- Employee username/password se login karo
- Face camera pe dikhao aur register karo

### 5. Frontend Kholo
- `frontend/login.html` browser mein kholo
- Username + Password + Face verify karke login karo

---

## Features
- ✅ Face Verification (face-api.js)
- ✅ 8 Hour Shift Timer
- ✅ 1 Hour Break Management
- ✅ Attendance History (30 days)
- ✅ Admin Panel
- ✅ Login/Logout with Summary
