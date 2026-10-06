# Employee Leave Management System

A web application where employees apply for leave and managers approve or reject
requests. Built with **Python 3, Flask, SQLAlchemy and MySQL**, with a server-rendered
UI (HTML, CSS, Jinja2) and a JSON REST API.

## Features

**Employee**
- Login / logout and a personal dashboard
- View Casual, Sick and Earned leave balances
- Apply for leave (type, start date, end date, reason)
- Automatic leave-day calculation (working days, Monday-Friday, inclusive)
- Overlapping leave requests are blocked
- Leave history with Pending / Approved / Rejected status and rejection reasons

**Manager**
- Login / logout and a manager dashboard
- View all employees (with their leave balances)
- View all leave requests, pending requests and full leave history (filter by status / employee)
- Approve leave (balance is deducted automatically) or reject it with a reason

**Security**
- Passwords hashed with Werkzeug, never stored in plain text
- Flask sessions, role-based route protection (employee vs manager)
- CSRF token on every HTML form
- Database credentials and secret key read from environment variables
- Server-side validation of all inputs (forms and API)

## Project Structure

```
employee-leave-management/
├── app.py                 # App factory, error handlers, CSRF, demo-data seeding
├── config.py              # Configuration from environment variables
├── requirements.txt
├── .env.example
├── database.sql           # MySQL schema + sample data
├── models/                # SQLAlchemy models (User, LeaveRequest, LeaveBalance)
├── routes/                # auth, employee, manager and REST API blueprints
├── templates/             # Jinja2 templates
└── static/css/style.css
```

## Installation

**Requirements:** Python 3.9+ and MySQL 5.7+/8.x (or MariaDB).

1. **Create a virtual environment and install dependencies**
   ```bash
   cd employee-leave-management
   python -m venv venv
   # Windows:      venv\Scripts\activate
   # macOS/Linux:  source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Create the database**

   Option A - schema and sample data from the SQL file (recommended):
   ```bash
   mysql -u root -p < database.sql
   ```
   Option B - only create an empty database; the app creates the tables and
   demo users automatically on first start:
   ```sql
   CREATE DATABASE leave_management CHARACTER SET utf8mb4;
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env        # Windows: copy .env.example .env
   ```
   Edit `.env` and set `SECRET_KEY`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`.

## Run

```bash
python app.py
```

Open <http://127.0.0.1:5000> in your browser.

## Sample Logins

| Role     | Email                 | Password      |
|----------|-----------------------|---------------|
| Manager  | manager@company.com   | Manager@123   |
| Employee | employee@company.com  | Employee@123  |
| Employee | anita@company.com     | Employee@123  |
| Employee | rahul@company.com     | Employee@123  |

Change these passwords before using the app anywhere other than your own machine.

## Business Rules

- Default balances: Casual 12, Sick 10, Earned 15 days.
- Days are counted Monday-Friday, inclusive; a request made up only of weekend days is rejected.
- Start date cannot be in the past; end date cannot be before the start date; maximum span is 90 days.
- A new request cannot overlap an existing **Pending** or **Approved** request.
- A request cannot exceed the available balance (balance minus days reserved by pending requests of the same type).
- Balance is deducted when a manager **approves** a request. Only pending requests can be approved or rejected.
- Rejection requires a reason (5-300 characters). Leave reason is 5-500 characters.

## REST API Documentation

Base URL: `http://127.0.0.1:5000/api`

The API uses the same Flask **session cookie** as the website: call `POST /api/login`
first and send the returned cookie with later requests. All request bodies must be JSON
(`Content-Type: application/json`). Errors return `{"error": "message"}` with a suitable
HTTP status code (400, 401, 403, 404, 409).

| Method | Endpoint                    | Access            | Description                                  |
|--------|-----------------------------|-------------------|----------------------------------------------|
| POST   | `/api/login`                | Public            | Log in and start a session                   |
| POST   | `/api/logout`               | Logged in         | End the session                              |
| GET    | `/api/leaves`               | Logged in         | Employee: own leaves. Manager: all leaves    |
| POST   | `/api/leaves`               | Employee          | Apply for leave                              |
| GET    | `/api/leaves/<id>`          | Owner or manager  | Get one leave request                        |
| PUT    | `/api/leaves/<id>/approve`  | Manager           | Approve a pending request                    |
| PUT    | `/api/leaves/<id>/reject`   | Manager           | Reject a pending request (reason required)   |
| GET    | `/api/employees`            | Manager           | List employees with leave balances           |
| GET    | `/api/employees/<id>`       | Manager or self   | Get one employee with leave balance          |

`GET /api/leaves` accepts optional query parameters: `status` (`Pending`, `Approved`,
`Rejected`) and, for managers, `user_id`.

### Examples (curl)

```bash
# Login (store the session cookie in cookies.txt)
curl -c cookies.txt -X POST http://127.0.0.1:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email": "employee@company.com", "password": "Employee@123"}'
```
Response `200`:
```json
{
  "message": "Login successful.",
  "user": {"id": 2, "name": "John Doe", "email": "employee@company.com", "role": "employee", "created_at": "..."}
}
```

```bash
# Apply for leave (employee)
curl -b cookies.txt -X POST http://127.0.0.1:5000/api/leaves \
  -H "Content-Type: application/json" \
  -d '{"leave_type": "Casual", "start_date": "2026-12-01", "end_date": "2026-12-03", "reason": "Personal work"}'
```
Response `201`:
```json
{
  "message": "Leave request submitted.",
  "leave": {
    "id": 7, "user_id": 2,
    "employee": {"id": 2, "name": "John Doe", "email": "employee@company.com"},
    "leave_type": "Casual", "start_date": "2026-12-01", "end_date": "2026-12-03",
    "days": 3, "reason": "Personal work", "status": "Pending",
    "rejection_reason": null, "applied_at": "...", "updated_at": "..."
  }
}
```
Validation failure `400`:
```json
{"error": "Validation failed.", "details": ["Start date cannot be in the past."]}
```

```bash
# List leaves, filtered (employee sees only their own)
curl -b cookies.txt "http://127.0.0.1:5000/api/leaves?status=Pending"

# Get one leave
curl -b cookies.txt http://127.0.0.1:5000/api/leaves/1

# Manager: login, approve and reject
curl -c mgr.txt -X POST http://127.0.0.1:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email": "manager@company.com", "password": "Manager@123"}'

curl -b mgr.txt -X PUT http://127.0.0.1:5000/api/leaves/3/approve

curl -b mgr.txt -X PUT http://127.0.0.1:5000/api/leaves/5/reject \
  -H "Content-Type: application/json" \
  -d '{"rejection_reason": "Team deadline during these dates."}'

# Manager: employees
curl -b mgr.txt http://127.0.0.1:5000/api/employees
curl -b mgr.txt http://127.0.0.1:5000/api/employees/2

# Logout
curl -b cookies.txt -X POST http://127.0.0.1:5000/api/logout
```

Status codes: `200` OK, `201` Created, `400` invalid input, `401` not logged in,
`403` wrong role / not your data, `404` not found, `409` the request is no longer pending
or the balance is insufficient.

## Database Schema

- `users` (id, name, email, password, role, created_at)
- `leave_balances` (id, user_id -> users.id, casual_leave, sick_leave, earned_leave)
- `leave_requests` (id, user_id -> users.id, leave_type, start_date, end_date, days, reason,
  status, rejection_reason, applied_at, updated_at)

Relationships: one user has one leave balance and many leave requests; deleting a user
cascades to both tables.

## Troubleshooting

- **"Could not connect to the database"** - make sure MySQL is running and the values in `.env` are correct.
- **`Access denied for user`** - check `DB_USER` / `DB_PASSWORD` in `.env`.
- **`Unknown database 'leave_management'`** - run `mysql -u root -p < database.sql` or create the database manually.
- **Forms say "bad request / expired"** - reload the page (the session or CSRF token expired).
