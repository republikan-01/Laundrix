from functools import wraps
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
import secrets
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from ..extensions import db
from ..models import (User, Service, Booking, Payment, Order, OrderEvent, DeliveryPersonnel,
                      Complaint, STEPS, STEP_KEYS, Promotion, Review)
from ..services.notify import notify

bp = Blueprint("admin", __name__)
LABELS = dict(STEPS)


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if current_user.role != "admin":
            return jsonify(error="Administrators only."), 403
        return f(*a, **kw)
    return wrapper


@bp.get("/stats")
@admin_required
def stats():
    revenue = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter_by(status="success").scalar()
    return jsonify(
        customers=User.query.filter_by(role="customer").count(),
        bookings=Booking.query.count(),
        awaiting_payment=Booking.query.filter_by(status="pending").count(),
        ongoing=Order.query.filter(Order.status != "delivered").count(),
        completed=Order.query.filter_by(status="delivered").count(),
        revenue=float(revenue),
        refund_requests=Payment.query.filter_by(refund_status="requested").count(),
        reviews=Review.query.count())


@bp.get("/orders")
@admin_required
def orders():
    rows = Order.query.order_by(Order.id.desc()).all()
    return jsonify(orders=[dict(
        id=o.id, reference=o.booking.reference, customer=o.booking.customer.full_name,
        phone=o.booking.customer.phone, where=f"{o.booking.pickup_location}: {o.booking.building_details}",
        pickup_at=o.booking.pickup_at.isoformat(), delivery_date=o.booking.delivery_date.isoformat(),
        status=o.status, pickup_staff_id=o.pickup_staff_id, delivery_staff_id=o.delivery_staff_id,
        total=float(o.booking.total_amount),
        tracking_url=(f"/rider/{o.delivery_staff.tracking_token}" if o.delivery_staff and o.delivery_staff.tracking_token else None),
        rider_lat=o.delivery_staff.current_lat if o.delivery_staff else None,
        rider_lng=o.delivery_staff.current_lng if o.delivery_staff else None) for o in rows], steps=STEPS)


@bp.patch("/orders/<int:order_id>")
@admin_required
def update_order(order_id):
    o = db.get_or_404(Order, order_id)
    d = request.get_json(silent=True) or {}
    new = d.get("status")
    if new:
        if new not in STEP_KEYS or STEP_KEYS.index(new) <= STEP_KEYS.index(o.status):
            return jsonify(error="Status can only move forward."), 422
        o.status = new
        o.events.append(OrderEvent(status=new))
        notify(o.booking.user_id, f"{o.booking.reference}: {LABELS[new]}.")
    for field in ("pickup_staff_id", "delivery_staff_id"):
        if field in d:
            sid = d[field] or None
            if sid and not db.session.get(DeliveryPersonnel, sid):
                return jsonify(error="Unknown staff member."), 422
            setattr(o, field, sid)
    db.session.commit()
    return jsonify(message="Order updated.")


@bp.get("/customers")
@admin_required
def customers():
    rows = User.query.filter_by(role="customer").order_by(User.id.desc()).all()
    return jsonify(customers=[dict(id=u.id, name=u.full_name, email=u.email, phone=u.phone,
                                   type=u.customer_type, active=u.is_active_account,
                                   bookings=u.bookings.count()) for u in rows])


@bp.post("/customers/<int:uid>/toggle")
@admin_required
def toggle_customer(uid):
    u = User.query.filter_by(id=uid, role="customer").first_or_404()  # admins can't be toggled here
    u.is_active_account = not u.is_active_account
    db.session.commit()
    return jsonify(active=u.is_active_account)


@bp.get("/payments")
@admin_required
def payments():
    rows = Payment.query.order_by(Payment.id.desc()).limit(200).all()
    return jsonify(payments=[dict(reference=p.reference, booking=p.booking.reference,
                                  customer=p.booking.customer.full_name, amount=float(p.amount),
                                  status=p.status, channel=p.channel,
                                  at=(p.paid_at or p.created_at).isoformat()) for p in rows])


@bp.get("/services")
@admin_required
def services():
    return jsonify(services=[dict(s.to_dict(), is_active=s.is_active) for s in Service.query.order_by(Service.id)])


def _service_fields(s, d):
    try:
        price = Decimal(str(d.get("price")))
    except InvalidOperation:
        price = Decimal("-1")
    name = (d.get("name") or "").strip()
    if not name or price <= 0 or d.get("unit") not in ("kg", "item"):
        return False
    s.name, s.price, s.unit = name, price, d["unit"]
    s.description = (d.get("description") or "").strip()[:255]
    if "is_active" in d:
        s.is_active = bool(d["is_active"])
    return True


@bp.post("/services")
@admin_required
def add_service():
    s = Service()
    if not _service_fields(s, request.get_json(silent=True) or {}):
        return jsonify(error="Enter a name, a unit (kg or item) and a price above zero."), 422
    if Service.query.filter_by(name=s.name).first():
        return jsonify(error="A service with this name already exists."), 409
    db.session.add(s)
    db.session.commit()
    return jsonify(message="Service added."), 201


@bp.put("/services/<int:sid>")
@admin_required
def edit_service(sid):
    s = db.get_or_404(Service, sid)
    if not _service_fields(s, request.get_json(silent=True) or {}):
        return jsonify(error="Enter a name, a unit (kg or item) and a price above zero."), 422
    db.session.commit()
    return jsonify(message="Service updated.")


@bp.get("/staff")
@admin_required
def staff():
    return jsonify(staff=[dict(id=p.id, name=p.name, phone=p.phone, active=p.is_active, tracking_url=(f"/rider/{p.tracking_token}" if p.tracking_token else None))
                          for p in DeliveryPersonnel.query.order_by(DeliveryPersonnel.id)])


@bp.post("/staff")
@admin_required
def add_staff():
    d = request.get_json(silent=True) or {}
    name, phone = (d.get("name") or "").strip(), (d.get("phone") or "").strip()
    if len(name) < 2 or len(phone) < 7:
        return jsonify(error="Enter the staff member's name and phone number."), 422
    db.session.add(DeliveryPersonnel(name=name, phone=phone, tracking_token=secrets.token_urlsafe(32)))
    db.session.commit()
    return jsonify(message="Staff member added."), 201


@bp.post("/staff/<int:pid>/toggle")
@admin_required
def toggle_staff(pid):
    p = db.get_or_404(DeliveryPersonnel, pid)
    p.is_active = not p.is_active
    db.session.commit()
    return jsonify(active=p.is_active)


@bp.get("/complaints")
@admin_required
def complaints():
    rows = Complaint.query.order_by(Complaint.status.desc(), Complaint.id.desc()).all()
    return jsonify(complaints=[dict(id=c.id, customer=c.user.full_name, message=c.message,
                                    status=c.status, reply=c.admin_reply,
                                    at=c.created_at.isoformat()) for c in rows])


@bp.post("/complaints/<int:cid>/reply")
@admin_required
def reply_complaint(cid):
    c = db.get_or_404(Complaint, cid)
    reply = ((request.get_json(silent=True) or {}).get("reply") or "").strip()[:1000]
    if not reply:
        return jsonify(error="Write a reply first."), 422
    c.admin_reply, c.status = reply, "resolved"
    notify(c.user_id, "Laundrix replied to your complaint. Check your dashboard.")
    db.session.commit()
    return jsonify(message="Reply sent.")


@bp.get("/analytics")
@admin_required
def analytics():
    now = datetime.utcnow(); start = now - timedelta(days=29)
    daily = []
    for i in range(30):
        day = (start + timedelta(days=i)).date()
        amount = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.status == "success", func.date(Payment.paid_at) == day).scalar()
        daily.append({"date": day.isoformat(), "revenue": float(amount)})
    return jsonify(daily=daily, order_statuses=[{"status": k, "count": Order.query.filter_by(status=k).count()} for k, _ in STEPS])

@bp.get("/promotions")
@admin_required
def promotions():
    rows = Promotion.query.order_by(Promotion.id.desc()).all()
    return jsonify(promotions=[dict(id=p.id, code=p.code, discount_percent=float(p.discount_percent),
        active=p.is_active, uses=p.uses, max_uses=p.max_uses,
        expires_at=p.expires_at.isoformat() if p.expires_at else None) for p in rows])

@bp.post("/promotions")
@admin_required
def add_promotion():
    d = request.get_json(silent=True) or {}; code = (d.get("code") or "").strip().upper()
    try: percent = Decimal(str(d.get("discount_percent")))
    except InvalidOperation: percent = Decimal("0")
    if not code or len(code) > 32 or not (Decimal("0") < percent <= Decimal("100")):
        return jsonify(error="Enter a code and discount between 0.01% and 100%."), 422
    if Promotion.query.filter_by(code=code).first(): return jsonify(error="That promotion code already exists."), 409
    db.session.add(Promotion(code=code, discount_percent=percent, max_uses=d.get("max_uses") or None))
    db.session.commit(); return jsonify(message="Promotion created."), 201

@bp.post("/promotions/<int:pid>/toggle")
@admin_required
def toggle_promotion(pid):
    p = db.get_or_404(Promotion, pid); p.is_active = not p.is_active
    db.session.commit(); return jsonify(message="Promotion updated.", active=p.is_active)

@bp.get("/reviews")
@admin_required
def reviews():
    rows = Review.query.order_by(Review.id.desc()).all()
    return jsonify(reviews=[dict(customer=r.user.full_name, booking=r.booking.reference,
        rating=r.rating, comment=r.comment or "", at=r.created_at.isoformat()) for r in rows])

@bp.get("/refunds")
@admin_required
def refunds():
    rows = Payment.query.filter(Payment.refund_status != "none").order_by(Payment.id.desc()).all()
    return jsonify(refunds=[dict(id=p.id, booking=p.booking.reference, customer=p.booking.customer.full_name,
        amount=float(p.amount), status=p.refund_status, note=p.refund_note or "") for p in rows])

@bp.patch("/refunds/<int:payment_id>")
@admin_required
def update_refund(payment_id):
    p = db.get_or_404(Payment, payment_id); status = (request.get_json(silent=True) or {}).get("status")
    if status not in ("approved", "rejected", "refunded") or p.refund_status not in ("requested", "approved"):
        return jsonify(error="Invalid refund status transition."), 422
    p.refund_status = status
    notify(p.booking.user_id, f"Refund update for {p.booking.reference}: {status}.")
    db.session.commit()
    return jsonify(message=f"Refund marked {status}. Note: marking refunded does not transfer money; process the refund in Paystack.")
