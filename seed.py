import os, secrets
from app import create_app
from app.extensions import db
from app.models import Service, User, DeliveryPersonnel

SERVICES = [
    ("Wash & Fold", "Washed, dried and folded", "kg", 1200),
    ("Wash & Iron", "Washed, dried and pressed", "kg", 1800),
    ("Ironing Only", "Pressed and hung or folded", "item", 200),
    ("Bedding & Duvets", "Sheets, duvets and blankets", "item", 1500),
    ("Dry Cleaning", "Suits, gowns and delicate wear", "item", 3000),
]
app = create_app()
with app.app_context():
    for n, d, u, p in SERVICES:
        if not Service.query.filter_by(name=n).first():
            db.session.add(Service(name=n, description=d, unit=u, price=p))
    if not DeliveryPersonnel.query.first():
        db.session.add(DeliveryPersonnel(name="Demo Rider", phone="08011112222", tracking_token=secrets.token_urlsafe(32)))
    for rider in DeliveryPersonnel.query.filter_by(tracking_token=None).all():
        rider.tracking_token = secrets.token_urlsafe(32)
    email = os.environ["ADMIN_EMAIL"].lower()
    if not User.query.filter_by(email=email).first():
        admin = User(full_name="Laundrix Admin", email=email, phone="08000000000", role="admin")
        admin.set_password(os.environ["ADMIN_PASSWORD"])
        db.session.add(admin)
    db.session.commit()
    print("Seeded services and admin account.")
