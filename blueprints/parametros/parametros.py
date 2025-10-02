# blueprints/parametros/parametros.py
"""
CRUD de parâmetros de proposta (visível a administradores e gestores).
"""

from functools import wraps
from flask import (
    render_template, redirect, url_for, flash,
    request, session
)

from blueprints.auth import login_required          # ← usa seu decorator
from blueprints.parametros import parametros_bp

from models import db, ParamOption, ParamCategory, User
from forms import ParamOptionForm


# ------------------------------------------------------------------
# Decorador: apenas administradores ou gestores
# ------------------------------------------------------------------
def gestor_ou_admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("tipo") not in ("admin", "administrador", "gestor"):
            flash("Acesso restrito!", "danger")
            return redirect(url_for('propostas_bp.historico_propostas'))
        return f(*args, **kwargs)
    return wrapper


# ------------------------------------------------------------------
# Listar + criar parâmetros
# ------------------------------------------------------------------
@parametros_bp.route('/parametros', methods=['GET', 'POST'])
@login_required
@gestor_ou_admin_required
def listar_parametros():
    form = ParamOptionForm()

    if form.validate_on_submit():
        user = User.query.get(session.get("usuario_id"))  # usuário logado
        novo_valor = ParamOption(
            category=form.category.data,
            label=form.label.data,
            created_by=user
        )
        db.session.add(novo_valor)
        db.session.commit()
        flash('Opção criada com sucesso!', 'success')
        return redirect(url_for('.listar_parametros'))

    parametros = ParamOption.query.order_by(
        ParamOption.category, ParamOption.label
    ).all()
    return render_template(
        'admin_parametros.html',
        form=form,
        parametros=parametros
    )


# ------------------------------------------------------------------
# Deletar parâmetro
# ------------------------------------------------------------------
@parametros_bp.route('/parametros/<int:id>/delete', methods=['POST'])
@login_required
@gestor_ou_admin_required
def deletar_parametro(id):
    opt = ParamOption.query.get_or_404(id)
    db.session.delete(opt)
    db.session.commit()
    flash('Opção removida.', 'info')
    return redirect(url_for('.listar_parametros'))
