import secrets
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from ..extensions import db, csrf
from ..models import Booking, Payment, Order, OrderEvent
from ..services import paystack
from ..services.notify import notify

bp = Blueprint("payments", __name__)


def settle(payment_id, data):
    """Idempotent. Marks a payment successful ONLY if Paystack confirms status, currency and exact amount."""
    p = Payment.query.filter_by(id=payment_id).with_for_update().first()
    if p.status == "success":
        return True
    paid_ok = (data.get("status") == "success" and data.get("currency") == "NGN"
               and int(data.get("amount", 0)) == int(p.amount * 100))
    if not paid_ok:
        if data.get("status") in ("failed", "abandoned"):
            p.status = "failed"
        db.session.commit()
        return False
    p.status, p.paid_at, p.channel = "success", datetime.utcnow(), data.get("channel")
    b = p.booking
    b.status = "confirmed"
    if not b.order:
        o = Order(booking=b, status="booking_confirmed")
        o.events.append(OrderEvent(status="booking_confirmed"))
        db.session.add(o)
    notify(b.user_id, f"Payment received for {b.reference}. Your booking is confirmed.")
    db.session.commit()
    return True


@bp.post("/initialize")
@login_required
def initialize():
    d = request.get_json(silent=True) or {}
    b = Booking.query.filter_by(id=d.get("booking_id"), user_id=current_user.id).first_or_404("Booking not found.")
    if b.status != "pending" or any(x.status == "success" for x in b.payments):
        return jsonify(error="This booking cannot be paid for."), 409
    ref = "LXP" + secrets.token_hex(8).upper()
    p = Payment(booking_id=b.id, reference=ref, amount=b.total_amount)  # amount comes from DB only
    db.session.add(p)
    db.session.commit()
    try:
        data = paystack.initialize(current_user.email, int(p.amount * 100), ref,
                                   current_app.config["APP_BASE_URL"] + "/payment/callback")
    except Exception as e:
        current_app.logger.error("Paystack init failed: %s", e)
        return jsonify(error="Payment could not be started. Please try again."), 502
    return jsonify(authorization_url=data["authorization_url"], reference=ref)


@bp.get("/verify")
@login_required
def verify():
    ref = request.args.get("reference", "")
    p = Payment.query.filter_by(reference=ref).first_or_404("Payment not found.")
    if p.booking.user_id != current_user.id:
        return jsonify(error="Payment not found."), 404
    try:
        ok = settle(p.id, paystack.verify(ref))
    except Exception as e:
        current_app.logger.error("Paystack verify failed: %s", e)
        return jsonify(error="We could not confirm this payment yet. Refresh in a moment."), 502
    return jsonify(success=ok, booking_id=p.booking_id, reference=p.booking.reference)


@bp.post("/webhook")
@csrf.exempt
def webhook():
    raw = request.get_data()
    if not paystack.valid_signature(raw, request.headers.get("X-Paystack-Signature")):
        return jsonify(error="Invalid signature."), 401
    event = request.get_json(silent=True) or {}
    if event.get("event") == "charge.success":
        data = event.get("data", {})
        p = Payment.query.filter_by(reference=data.get("reference")).first()
        if p:
            settle(p.id, data)
    return "", 200
