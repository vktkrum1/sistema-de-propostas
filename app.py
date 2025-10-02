# app.py
from flask import Flask, redirect, url_for
from models import db

# Blueprints
from blueprints.auth import auth_bp, login_required
from blueprints.propostas import propostas_bp
from blueprints.equipamentos import equipamentos_bp
from blueprints.parametros import parametros_bp
from api import api_bp

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # ------------------------
    # Carregamento de config
    # ------------------------
    loaded = False
    # 1) Se houver classe Config dentro de config.py, usa
    try:
        from config import Config as _Config  # noqa
        app.config.from_object(_Config)
        loaded = True
    except Exception:
        pass

    # 2) Caso não exista a classe, tenta carregar o arquivo config.py direto
    if not loaded:
        try:
            app.config.from_pyfile("config.py")
            loaded = True
        except Exception:
            pass

    # 3) Defaults (se algo faltar)
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///app.db")
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("SECRET_KEY", "dev-change-me")

    # DB
    db.init_app(app)

    # Flask-Migrate (opcional)
    try:
        from flask_migrate import Migrate  # noqa
        Migrate(app, db)
    except Exception:
        pass

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(propostas_bp)
    app.register_blueprint(equipamentos_bp)
    app.register_blueprint(parametros_bp)
    app.register_blueprint(api_bp)  # já define /api internamente

    # Rota inicial → Nova Proposta (protegida)
    @app.route("/")
    @login_required
    def index():
        return redirect(url_for("propostas_bp.nova_proposta"))

    # Cria admin padrão se sua função existir
    try:
        from blueprints.auth import criar_admin_padrao  # noqa
        with app.app_context():
            criar_admin_padrao()
    except Exception:
        # silencioso se a função não existir
        pass

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5910, debug=True)
