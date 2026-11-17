import re
from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required
from ..extensions import db
from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from ..models import User
from ..services.mailer import send_email

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{10,15}$")


@bp.post("/register")
def register():
    d = request.get_json(silent=True) or {}
    name = (d.get("full_name") or "").strip()
    email = (d.get("email") or "").strip().lower()
    phone = re.sub(r"[\s-]", "", d.get("phone") or "")
    pw = d.get("password") or ""
    ctype = d.get("customer_type")
    errors = {}
    if len(name) < 2 or len(name) > 120:
        errors["full_name"] = "Enter your full name."
    if not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    if not PHONE_RE.match(phone):
        errors["phone"] = "Enter a valid phone number, e.g. 08012345678."
    if len(pw) < 8 or not re.search(r"\d", pw) or not re.search(r"[A-Za-z]", pw):
        errors["password"] = "Use at least 8 characters with letters and numbers."
    if ctype not in ("student", "lecturer", "staff"):
        errors["customer_type"] = "Choose who you are."
    if not errors and User.query.filter_by(email=email).first():
        errors["email"] = "An account with this email already exists."
    if errors:
        return jsonify(error="Please fix the highlighted fields.", fields=errors), 422
    user = User(full_name=name, email=email, phone=phone, customer_type=ctype, role="customer")
    user.set_password(pw)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify(message="Account created.", redirect="/dashboard"), 201


@bp.post("/login")
def login():
    d = request.get_json(silent=True) or {}
    user = User.query.filter_by(email=(d.get("email") or "").strip().lower()).first()
    if not user:
        return jsonify(error="User not found. Please create a Laundrix account first.", code="USER_NOT_FOUND"), 404
    if not user.is_active:
        return jsonify(error="This account has been deactivated. Please contact Laundrix support."), 403
    if not user.check_password(d.get("password") or ""):
        return jsonify(error="Invalid credentials. Please check your password and try again.", code="INVALID_CREDENTIALS"), 401
    login_user(user)
    return jsonify(message="Logged in.", redirect="/admin" if user.role == "admin" else "/dashboard")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return jsonify(message="Logged out.", redirect="/")


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="pw-reset")


@bp.post("/forgot")
def forgot():
    email = ((request.get_json(silent=True) or {}).get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if user and user.is_active:
        token = _serializer().dumps({"id": user.id, "h": user.password_hash[-12:]})  # dies once password changes
        link = f"{current_app.config['APP_BASE_URL']}/reset/{token}"
        send_email(user.email, "Reset your Laundrix password",
                   f"Use this link within 1 hour to reset your password:\n{link}\n\n"
                   "If you did not ask for this, ignore this email. Laundrix never asks for your password or OTP on WhatsApp.")
    # Same answer either way so nobody can test which emails are registered.
    return jsonify(message="If that email is registered, a reset link is on its way.")


@bp.post("/reset")
def reset():
    d = request.get_json(silent=True) or {}
    pw = d.get("password") or ""
    try:
        data = _serializer().loads(d.get("token", ""), max_age=3600)
    except (BadSignature, SignatureExpired):
        return jsonify(error="This reset link is invalid or has expired. Request a new one."), 400
    user = db.session.get(User, data["id"])
    if not user or user.password_hash[-12:] != data["h"]:
        return jsonify(error="This reset link has already been used."), 400
    if len(pw) < 8 or not re.search(r"\d", pw) or not re.search(r"[A-Za-z]", pw):
        return jsonify(error="Use at least 8 characters with letters and numbers.", fields={"password": "Too weak."}), 422
    user.set_password(pw)
    db.session.commit()
    return jsonify(message="Password updated.", redirect="/login")
