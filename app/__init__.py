import os
from flask import Flask, jsonify, request, url_for
from .config import Config
from .extensions import db, migrate, login_manager, csrf


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    if os.environ.get("BEHIND_PROXY") == "1":  # set on a host that terminates HTTPS for you
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401
    from .main.routes import bp as main_bp
    from .auth.routes import bp as auth_bp
    from .api.routes import bp as api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(api_bp, url_prefix="/api")
    from .payments.routes import bp as pay_bp
    from .admin.routes import bp as admin_bp
    app.register_blueprint(pay_bp, url_prefix="/api/payments")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    @app.context_processor
    def inject_globals():
        import datetime

        def photo(name):  # URL of a real photo dropped into static/images, or None (templates then show an icon)
            for ext in ("webp", "jpg", "jpeg", "png"):
                if os.path.exists(os.path.join(app.static_folder, "images", f"{name}.{ext}")):
                    return url_for("static", filename=f"images/{name}.{ext}")
            return None

        return {"whatsapp_number": app.config["WHATSAPP_NUMBER"], "photo": photo,
                "year": datetime.date.today().year}

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify(error="Please log in to continue."), 401
        from flask import redirect, url_for
        return redirect(url_for("main.login_page"))

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(500)
    def handle_error(e):
        code = getattr(e, "code", 500)
        if request.path.startswith("/api/"):
            return jsonify(error=getattr(e, "description", "Server error")), code
        return e

    return app
