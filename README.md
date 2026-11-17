# Laundrix – Laundry booking and operations platform

Flask + MySQL application with customer booking, Paystack payments, order-stage tracking, admin operations, delivery GPS sharing, discount codes, refund requests, customer reviews, analytics, and optional Twilio SMS/WhatsApp notifications.

## 1. Requirements
- Python 3.11 or newer
- MySQL 8 (recommended) or another SQLAlchemy-supported database for local testing
- A Paystack account for online payments (use test keys first)
- HTTPS on the deployed website for browser GPS permissions (localhost is allowed for development)

## 2. Installation

```bash
python -m venv venv
# Windows PowerShell: .\\venv\\Scripts\\Activate.ps1
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Create a MySQL database and database user:

```sql
CREATE DATABASE laundrix CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'laundrix_user'@'localhost' IDENTIFIED BY 'UseA_Strong_Password';
GRANT ALL PRIVILEGES ON laundrix.* TO 'laundrix_user'@'localhost';
```

Copy `.env.example` to `.env`, then set a unique `SECRET_KEY`, your `DATABASE_URL`, `ADMIN_EMAIL`, and a strong `ADMIN_PASSWORD`. Generate a secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Never commit or share `.env`. The archive intentionally does not include the original environment file or a virtual environment.

## 3. Database setup and upgrade

For a fresh database:

```bash
flask --app run.py db upgrade
python seed.py
```

The repository includes the initial schema migration and the new growth-features migration. For an existing Laundrix installation, back up the database first, then run the same `flask --app run.py db upgrade` command and `python seed.py`. Do not run `db init` again if the `migrations` folder already exists.

## 4. Start the application

```bash
python run.py
```

Open `http://127.0.0.1:5000`. Sign in with the admin email/password configured in `.env`; the admin account is created by `python seed.py`.

## 5. Admin dashboard

Open `/admin`. Admin-only API routes enforce the `admin` role. The dashboard includes:
- Orders: view bookings, update order stage, assign pickup and delivery staff
- Customers: view and activate/deactivate customer accounts
- Payments: view Paystack payment records
- Services and prices: create, edit, activate/deactivate services
- Delivery staff: add/disable riders and access their private GPS-sharing links
- Complaints: review and reply to customer complaints
- Analytics: 30-day daily revenue and order-stage totals
- Discount codes: create and activate/deactivate percentage promotions
- Refunds: review and update refund-request workflow
- Reviews: view customer ratings and comments

## 6. Rider GPS tracking

1. In Admin → Delivery staff, add a rider (or run `python seed.py` to generate a link for existing demo staff).
2. Assign that staff member as the delivery staff for an order.
3. Open the rider's **Rider GPS link** on the rider's phone while signed into a secure HTTPS website.
4. The rider taps **Start live location sharing** and allows location access. Keep the page open during the delivery.
5. The customer opens the order's Track page. The map refreshes automatically and shows the rider's most recent location.
6. The rider taps **Stop** after delivery. A location older than 10 minutes is hidden from customers.

The GPS link is a bearer secret: share it only with the intended rider. If it is exposed, deactivate the staff account and create a replacement staff record/link. Browser GPS requires user permission and HTTPS (except localhost). Location updates are sent while the rider portal is open; this is not background tracking.

## 7. SMS / WhatsApp notifications (optional)

In `.env`, configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM`. Set `TWILIO_CHANNEL=sms` for SMS or `TWILIO_CHANNEL=whatsapp` for WhatsApp. For WhatsApp, `TWILIO_FROM` must be an approved Twilio WhatsApp sender, and recipients must meet Twilio's WhatsApp messaging rules. Without credentials, the app continues to use in-app notifications only. Delivery depends on Twilio account configuration, templates/consent rules, and recipient phone formatting.

## 8. Paystack payments

Set `PAYSTACK_SECRET_KEY` to a Paystack test secret first and set `APP_BASE_URL` to your public URL. Configure Paystack's webhook URL as:

`APP_BASE_URL/api/payments/webhook`

For local webhook testing, expose the development server with a secure tunnel such as ngrok and set `APP_BASE_URL` to that HTTPS address. Never expose the Paystack secret key in frontend JavaScript.

Refund requests are collected in the admin dashboard. **Approving or marking a refund in Laundrix does not send money.** An admin must process the actual refund in Paystack, then mark it refunded in Laundrix.

## 9. Login behavior

- Email not found: HTTP 404 with `User not found. Please create a Laundrix account first.`
- Existing email + incorrect password: HTTP 401 with `Invalid credentials. Please check your password and try again.`
- Deactivated account: HTTP 403 with a support message.

## 10. Security and production checklist

- Use HTTPS and set `FLASK_ENV=production`.
- Use unique long secrets and a database user with only required privileges.
- Keep `.env`, database backups, Paystack keys and Twilio credentials private.
- Back up the database before applying migrations.
- Configure SMTP if password-reset email is required.
- Restrict access to rider GPS links; they act like passwords.
- Add rate limiting, monitoring, automated backups, and a formal privacy/consent notice before public launch.
- Test Paystack in test mode before switching to live credentials.

## API additions

- `POST /api/rider/location/<token>` – rider GPS update (token protected)
- `POST /api/rider/location/<token>/stop` – clear the rider's shared location
- `POST /api/reviews` – customer review after delivery
- `POST /api/payments/refund-request` – customer refund request
- `GET /api/admin/analytics` – admin analytics
- `GET, POST /api/admin/promotions` – list/create promotions
- `POST /api/admin/promotions/<id>/toggle` – activate/deactivate a promotion
- `GET /api/admin/refunds`, `PATCH /api/admin/refunds/<payment_id>` – refund workflow
- `GET /api/admin/reviews` – customer reviews
