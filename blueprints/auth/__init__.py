"""
Blueprint de autenticação.
Define:
    • auth_bp             – Blueprint principal
    • login_required      – decorator baseado em sessão
    • admin_required      – rotas apenas para admin
    • criar_admin_padrao  – cria usuário admin na 1ª execução
"""

from functools import wraps
from flask import (
    Blueprint, session, flash, redirect,
    url_for, request, jsonify
)
from werkzeug.security import generate_password_hash
from sqlalchemy import inspect                      # ← NOVO

from models import db, User

# ------------------------------------------------------------------
# Blueprint
# ------------------------------------------------------------------
auth_bp = Blueprint('auth_bp', __name__, template_folder='../templates')

# ------------------------------------------------------------------
# Decorators de proteção
# ------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("usuario_id"):
            return f(*args, **kwargs)

        # ---------- não logado ----------
        wants_html = request.accept_mimetypes.accept_html
        is_ajax    = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        if wants_html and not is_ajax:      # navegação normal
            flash("Please log in to access this page.", "danger")
            return redirect(url_for('auth_bp.login', next=request.path))

        # chamada programática → devolve JSON + 401
        return jsonify(error="login_required"), 401
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("tipo") != "admin":
            flash("Acesso restrito aos administradores.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ------------------------------------------------------------------
# Utilitário: cria usuário admin se não existir
# ------------------------------------------------------------------
def criar_admin_padrao():
    """
    Durante migrações iniciais, a coluna users.prox_num pode ainda não
    existir. Fazemos duas verificações:
      1. A tabela users já foi criada?
      2. A coluna prox_num já existe?
    Se qualquer uma falhar, saímos silenciosamente.
    """
    insp = inspect(db.engine)
    if 'users' not in insp.get_table_names():
        return                                # primeira migração ainda
    if 'prox_num' not in [c['name'] for c in insp.get_columns('users')]:
        return                                # coluna ainda não criada

    if not User.query.filter_by(usuario="admin").first():
        admin = User(
            usuario="admin",
            nome_completo="Administrador",
            senha_hash=generate_password_hash("admin"),
            tipo="admin",
            email="admin@example.com",
            prox_num=1                        # novo campo padrão
        )
        db.session.add(admin)
        db.session.commit()

# ------------------------------------------------------------------
# Importa rotas (mantido no fim para evitar import circular)
# ------------------------------------------------------------------
from . import login      # noqa: E402,F401
from . import usuarios   # noqa: E402,F401
