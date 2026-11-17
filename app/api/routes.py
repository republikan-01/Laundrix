from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..extensions import db, csrf
from ..models import Service, Booking, BookingItem, Notification, Complaint, STEPS, STEP_KEYS, DeliveryPersonnel, Review, Order, Payment, Promotion
from ..auth.routes import PHONE_RE

bp = Blueprint("api", __name__)
LOCATIONS = ["Hostel", "Staff Quarters", "Faculty Building", "Other On-Campus"]


@bp.get("/services")
def services():
    rows = Service.query.filter_by(is_active=True).order_by(Service.id).all()
    return jsonify(services=[s.to_dict() for s in rows], locations=LOCATIONS)


@bp.post("/bookings")
@login_required
def create_booking():
    d = request.get_json(silent=True) or {}
    errors = {}
    location = d.get("pickup_location")
    details = (d.get("building_details") or "").strip()
    instructions = (d.get("instructions") or "").strip()[:500]
    if location not in LOCATIONS:
        errors["pickup_location"] = "Choose a pickup location."
    if not 3 <= len(details) <= 160:
        errors["building_details"] = "Enter your hostel/building and room (3-160 characters)."
    pickup_at = delivery = None
    try:
        pickup_at = datetime.fromisoformat(d.get("pickup_at", ""))
        if pickup_at <= datetime.now():
            errors["pickup_at"] = "Pickup time must be in the future."
    except ValueError:
        errors["pickup_at"] = "Choose a pickup date and time."
    try:
        delivery = date.fromisoformat(d.get("delivery_date", ""))
        if pickup_at and delivery < pickup_at.date():
            errors["delivery_date"] = "Delivery cannot be before pickup."
    except ValueError:
        errors["delivery_date"] = "Choose a delivery date."

    lines, total = [], Decimal("0")
    raw_items = d.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        errors["items"] = "Select at least one service."
    else:
        for it in raw_items:
            svc, qty = None, Decimal("0")
            if isinstance(it, dict):
                svc = db.session.get(Service, it.get("service_id")) if isinstance(it.get("service_id"), int) else None
                try:
                    qty = Decimal(str(it.get("quantity")))
                except InvalidOperation:
                    pass
            if not svc or not svc.is_active or not (Decimal("0") < qty <= Decimal("100")):
                errors["items"] = "Check your services and quantities (up to 100)."
                break
            lines.append(BookingItem(service_id=svc.id, quantity=qty, unit_price=svc.price))
            total += svc.price * qty  # price always from the database, never the client
    if errors:
        return jsonify(error="Please fix the highlighted fields.", fields=errors), 422

    promo = None
    code = (d.get("discount_code") or "").strip().upper()
    discount = Decimal("0")
    if code:
        promo = Promotion.query.filter_by(code=code, is_active=True).first()
        if not promo or (promo.expires_at and promo.expires_at < datetime.utcnow()) or (promo.max_uses and promo.uses >= promo.max_uses):
            return jsonify(error="This discount code is invalid or expired."), 422
        discount = (total * promo.discount_percent / Decimal("100")).quantize(Decimal("0.01"))
        promo.uses += 1
    final_total = max(Decimal("0"), total - discount)
    b = Booking(reference=Booking.new_reference(), user_id=current_user.id,
                pickup_location=location, building_details=details, pickup_at=pickup_at,
                delivery_date=delivery, instructions=instructions, total_amount=final_total,
                discount_code=code or None, discount_amount=discount, items=lines)
    db.session.add(b)
    db.session.commit()
    return jsonify(booking=b.to_dict()), 201


@bp.get("/bookings")
@login_required
def list_bookings():
    rows = current_user.bookings.order_by(Booking.created_at.desc()).all()
    return jsonify(bookings=[b.to_dict() for b in rows])


def _own_booking(booking_id):
    return Booking.query.filter_by(id=booking_id, user_id=current_user.id).first_or_404("Booking not found.")


@bp.get("/bookings/<int:booking_id>")
@login_required
def get_booking(booking_id):
    return jsonify(booking=_own_booking(booking_id).to_dict())


@bp.post("/bookings/<int:booking_id>/cancel")
@login_required
def cancel_booking(booking_id):
    b = _own_booking(booking_id)
    if b.status != "pending" or b.pickup_at <= datetime.now():
        return jsonify(error="This booking can no longer be cancelled."), 409
    b.status = "cancelled"
    db.session.commit()
    return jsonify(booking=b.to_dict())


@bp.get("/bookings/<int:booking_id>/tracking")
@login_required
def tracking(booking_id):
    b = _own_booking(booking_id)
    if not b.order:
        return jsonify(error="Tracking starts once your payment is confirmed."), 404
    seen = {e.status: e.created_at.isoformat() + "Z" for e in b.order.events}
    rider = b.order.delivery_staff
    location = None
    if rider and rider.current_lat is not None and rider.current_lng is not None and rider.location_updated_at and (datetime.utcnow() - rider.location_updated_at).total_seconds() <= 600:
        location = {"lat": rider.current_lat, "lng": rider.current_lng,
                    "updated_at": rider.location_updated_at.isoformat() + "Z" if rider.location_updated_at else None,
                    "rider_name": rider.name, "rider_phone": rider.phone}
    cur = STEP_KEYS.index(b.order.status)
    return jsonify(reference=b.reference, rider_location=location, steps=[
        dict(key=k, label=l, done=i <= cur, current=i == cur, at=seen.get(k)) for i, (k, l) in enumerate(STEPS)])


@bp.get("/notifications")
@login_required
def notifications():
    q = Notification.query.filter_by(user_id=current_user.id)
    rows = q.order_by(Notification.id.desc()).limit(15).all()
    return jsonify(unread=q.filter_by(is_read=False).count(), notifications=[
        dict(message=n.message, is_read=n.is_read, at=n.created_at.isoformat() + "Z") for n in rows])


@bp.post("/notifications/read")
@login_required
def mark_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify(message="ok")


@bp.get("/profile")
@login_required
def get_profile():
    u = current_user
    return jsonify(full_name=u.full_name, email=u.email, phone=u.phone, saved_location=u.saved_location or "",
                   notifications_enabled=u.notifications_enabled)


@bp.put("/profile")
@login_required
def update_profile():
    d = request.get_json(silent=True) or {}
    name, phone = (d.get("full_name") or "").strip(), (d.get("phone") or "").replace(" ", "")
    errors = {}
    if len(name) < 2:
        errors["full_name"] = "Enter your full name."
    if not PHONE_RE.match(phone):
        errors["phone"] = "Enter a valid phone number."
    if errors:
        return jsonify(error="Please fix the highlighted fields.", fields=errors), 422
    current_user.full_name, current_user.phone = name, phone
    current_user.saved_location = (d.get("saved_location") or "").strip()[:160] or None
    current_user.notifications_enabled = bool(d.get("notifications_enabled"))
    db.session.commit()
    return jsonify(message="Profile saved.")


@bp.post("/profile/password")
@login_required
def change_password():
    import re
    d = request.get_json(silent=True) or {}
    new = d.get("new_password") or ""
    if not current_user.check_password(d.get("current_password") or ""):
        return jsonify(error="Your current password is incorrect.", fields={"current_password": "Incorrect."}), 422
    if len(new) < 8 or not re.search(r"\d", new) or not re.search(r"[A-Za-z]", new):
        return jsonify(error="Use at least 8 characters with letters and numbers.", fields={"new_password": "Too weak."}), 422
    current_user.set_password(new)
    db.session.commit()
    return jsonify(message="Password changed.")


@bp.post("/complaints")
@login_required
def add_complaint():
    d = request.get_json(silent=True) or {}
    msg = (d.get("message") or "").strip()
    if not 5 <= len(msg) <= 1000:
        return jsonify(error="Describe the problem in 5-1000 characters.", fields={"message": "Too short."}), 422
    bid = d.get("booking_id")
    if bid and not Booking.query.filter_by(id=bid, user_id=current_user.id).first():
        return jsonify(error="Booking not found."), 404
    db.session.add(Complaint(user_id=current_user.id, booking_id=bid or None, message=msg))
    db.session.commit()
    return jsonify(message="Complaint received. We will reply on your dashboard."), 201


@bp.get("/complaints")
@login_required
def my_complaints():
    rows = Complaint.query.filter_by(user_id=current_user.id).order_by(Complaint.id.desc()).all()
    return jsonify(complaints=[dict(message=c.message, status=c.status, reply=c.admin_reply) for c in rows])


@bp.post("/reviews")
@login_required
def submit_review():
    d = request.get_json(silent=True) or {}
    booking = Booking.query.filter_by(id=d.get("booking_id"), user_id=current_user.id).first()
    try: rating = int(d.get("rating"))
    except (TypeError, ValueError): rating = 0
    if not booking or not booking.order or booking.order.status != "delivered":
        return jsonify(error="You can review an order only after it has been delivered."), 409
    if not 1 <= rating <= 5:
        return jsonify(error="Choose a rating from 1 to 5."), 422
    if Review.query.filter_by(booking_id=booking.id).first():
        return jsonify(error="You have already reviewed this order."), 409
    db.session.add(Review(user_id=current_user.id, booking_id=booking.id, rating=rating,
                          comment=(d.get("comment") or "").strip()[:1000]))
    db.session.commit()
    return jsonify(message="Thank you for reviewing Laundrix."), 201

@bp.post("/payments/refund-request")
@login_required
def refund_request():
    d = request.get_json(silent=True) or {}
    payment = Payment.query.join(Booking).filter(Payment.booking_id == d.get("booking_id"),
        Booking.user_id == current_user.id, Payment.status == "success").first()
    if not payment:
        return jsonify(error="No successful payment was found for this booking."), 404
    if payment.refund_status not in ("none", "rejected"):
        return jsonify(error="A refund request already exists for this payment."), 409
    payment.refund_status = "requested"
    payment.refund_note = (d.get("reason") or "Customer requested a refund.").strip()[:500]
    db.session.commit()
    return jsonify(message="Refund request submitted for admin review.")

@bp.post("/rider/location/<token>")
@csrf.exempt
def rider_location_update(token):
    rider = DeliveryPersonnel.query.filter_by(tracking_token=token, is_active=True).first()
    if not rider:
        return jsonify(error="Tracking link is invalid or disabled."), 404
    d = request.get_json(silent=True) or {}
    try: lat, lng = float(d.get("lat")), float(d.get("lng"))
    except (TypeError, ValueError): return jsonify(error="Valid latitude and longitude are required."), 422
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify(error="Coordinates are outside valid ranges."), 422
    rider.current_lat, rider.current_lng = lat, lng
    rider.location_updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(message="Location updated.")


@bp.post("/rider/location/<token>/stop")
@csrf.exempt
def rider_location_stop(token):
    rider = DeliveryPersonnel.query.filter_by(tracking_token=token).first()
    if not rider:
        return jsonify(error="Tracking link is invalid."), 404
    rider.current_lat = None
    rider.current_lng = None
    rider.location_updated_at = None
    db.session.commit()
    return jsonify(message="Location sharing stopped.")
