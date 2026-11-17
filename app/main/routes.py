from flask import Blueprint, render_template, abort, send_from_directory, current_app, make_response
from flask_login import login_required, current_user
from ..models import Service, Booking

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return render_template("index.html", services=Service.query.filter_by(is_active=True).all())


@bp.get("/login")
def login_page():
    return render_template("login.html")


@bp.get("/register")
def register_page():
    return render_template("register.html")


@bp.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@bp.get("/book")
@login_required
def book():
    return render_template("book.html")


def _own(booking_id):
    return Booking.query.filter_by(id=booking_id, user_id=current_user.id).first_or_404()


@bp.get("/forgot")
def forgot_page():
    return render_template("forgot.html")


@bp.get("/reset/<token>")
def reset_page(token):
    return render_template("reset.html", token=token)


@bp.get("/payment/callback")
@login_required
def payment_callback():
    return render_template("pay_callback.html")


@bp.get("/track/<int:booking_id>")
@login_required
def track(booking_id):
    return render_template("track.html", booking=_own(booking_id))


@bp.get("/receipt/<int:booking_id>")
@login_required
def receipt(booking_id):
    b = _own(booking_id)
    payment = next((p for p in b.payments if p.status == "success"), None)
    if not payment:
        abort(404)
    return render_template("receipt.html", booking=b, payment=payment)


@bp.get("/profile")
@login_required
def profile():
    return render_template("profile.html")


@bp.get("/admin")
@login_required
def admin():
    if current_user.role != "admin":
        abort(403)
    return render_template("admin.html")


@bp.get("/sw.js")
def service_worker():
    r = make_response(send_from_directory(current_app.static_folder, "sw.js", mimetype="application/javascript"))
    r.headers["Cache-Control"] = "no-cache"
    r.headers["Service-Worker-Allowed"] = "/"
    return r


@bp.get("/manifest.webmanifest")
def manifest():
    return send_from_directory(current_app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json")


@bp.get("/offline")
def offline():
    return render_template("offline.html")


@bp.get("/rider/<token>")
def rider_portal(token):
    from ..models import DeliveryPersonnel
    rider = DeliveryPersonnel.query.filter_by(tracking_token=token, is_active=True).first_or_404()
    return render_template("rider.html", rider=rider)
