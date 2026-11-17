import secrets
from datetime import datetime
import sqlalchemy as sa
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("customer", "admin"), nullable=False, default="customer")
    customer_type = db.Column(db.Enum("student", "lecturer", "staff"), nullable=True)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    saved_location = db.Column(db.String(160))
    notifications_enabled = db.Column(db.Boolean, nullable=False, default=True, server_default=sa.true())
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    bookings = db.relationship("Booking", backref="customer", lazy="dynamic")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)  # scrypt by default

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def is_active(self):
        return self.is_active_account


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Service(db.Model):
    __tablename__ = "services"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    description = db.Column(db.String(255))
    unit = db.Column(db.Enum("kg", "item"), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return dict(id=self.id, name=self.name, description=self.description,
                    unit=self.unit, price=float(self.price))


class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(16), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    pickup_location = db.Column(db.String(120), nullable=False)
    building_details = db.Column(db.String(160), nullable=False)
    pickup_at = db.Column(db.DateTime, nullable=False)
    delivery_date = db.Column(db.Date, nullable=False)
    instructions = db.Column(db.String(500))
    status = db.Column(db.Enum("pending", "confirmed", "cancelled"), nullable=False, default="pending")
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    discount_code = db.Column(db.String(32))
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    items = db.relationship("BookingItem", backref="booking", cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="booking")
    order = db.relationship("Order", backref="booking", uselist=False)

    @staticmethod
    def new_reference():
        return "LX" + secrets.token_hex(4).upper()

    def to_dict(self):
        return dict(
            id=self.id, reference=self.reference, status=self.status,
            pickup_location=self.pickup_location, building_details=self.building_details,
            pickup_at=self.pickup_at.isoformat(), delivery_date=self.delivery_date.isoformat(),
            instructions=self.instructions, total_amount=float(self.total_amount),
            created_at=self.created_at.isoformat(),
            paid=any(p.status == 'success' for p in self.payments),
            discount_code=self.discount_code, discount_amount=float(self.discount_amount or 0),
            order_status=self.order.status if self.order else None,
            items=[dict(service=i.service.name, quantity=float(i.quantity),
                        unit_price=float(i.unit_price)) for i in self.items])


class BookingItem(db.Model):
    __tablename__ = "booking_items"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    quantity = db.Column(db.Numeric(8, 2), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)  # price snapshot
    service = db.relationship("Service")


STEPS = [("booking_confirmed", "Booking confirmed"), ("picked_up", "Laundry picked up"),
         ("received", "Received at laundry facility"), ("washing", "Washing in progress"),
         ("ironing", "Ironing and folding"), ("ready", "Ready for delivery"),
         ("out_for_delivery", "Out for delivery"), ("delivered", "Delivered")]
STEP_KEYS = [k for k, _ in STEPS]


class DeliveryPersonnel(db.Model):
    __tablename__ = "delivery_personnel"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    tracking_token = db.Column(db.String(64), unique=True, index=True)
    current_lat = db.Column(db.Float)
    current_lng = db.Column(db.Float)
    location_updated_at = db.Column(db.DateTime)


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False, index=True)
    reference = db.Column(db.String(40), unique=True, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Enum("pending", "success", "failed"), nullable=False, default="pending")
    channel = db.Column(db.String(30))
    paid_at = db.Column(db.DateTime)
    refund_status = db.Column(db.Enum("none", "requested", "approved", "refunded", "rejected"), nullable=False, default="none")
    refund_note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), unique=True, nullable=False)
    status = db.Column(db.Enum(*STEP_KEYS), nullable=False, default="booking_confirmed")
    pickup_staff_id = db.Column(db.Integer, db.ForeignKey("delivery_personnel.id"))
    delivery_staff_id = db.Column(db.Integer, db.ForeignKey("delivery_personnel.id"))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    pickup_staff = db.relationship("DeliveryPersonnel", foreign_keys=[pickup_staff_id])
    delivery_staff = db.relationship("DeliveryPersonnel", foreign_keys=[delivery_staff_id])
    events = db.relationship("OrderEvent", backref="order", order_by="OrderEvent.id", cascade="all, delete-orphan")


class OrderEvent(db.Model):
    __tablename__ = "order_events"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    status = db.Column(db.Enum(*STEP_KEYS), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Complaint(db.Model):
    __tablename__ = "complaints"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"))
    message = db.Column(db.String(1000), nullable=False)
    status = db.Column(db.Enum("open", "resolved"), nullable=False, default="open")
    admin_reply = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User")


class Promotion(db.Model):
    __tablename__ = "promotions"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    discount_percent = db.Column(db.Numeric(5, 2), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    expires_at = db.Column(db.DateTime)
    max_uses = db.Column(db.Integer)
    uses = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), unique=True, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User")
    booking = db.relationship("Booking")
