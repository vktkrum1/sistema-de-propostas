"""
CRUD de usuários (painel de administração)
Rotas dentro do Blueprint auth_bp
URLs resultantes:
    • /auth/admin/usuarios              – listar & criar
    • /auth/editar_usuario/<id>         – editar via modal (GET/POST)
    • /auth/admin/usuarios/excluir/<id> – excluir (POST)
"""
from flask import (
    render_template, redirect, url_for, flash,
    request, jsonify, session
)
from werkzeug.security import generate_password_hash

from . import auth_bp, login_required, admin_required
from models import db, User
from forms import UserForm

# --------------------------------------------------------------------------- #
# Listar & criar usuários
# --------------------------------------------------------------------------- #
@auth_bp.route("/admin/usuarios", methods=["GET", "POST"])
@admin_required
def gerenciar_usuarios():
    form = UserForm()
    if form.validate_on_submit():
        if User.query.filter_by(usuario=form.usuario.data).first():
            flash("Este usuário já existe.", "warning")
        else:
            novo = User(
                usuario       = form.usuario.data,
                nome_completo = form.nome_completo.data,
                email         = form.email.data,
                tipo          = form.tipo.data,
                senha_hash    = generate_password_hash(form.senha.data),
                prox_num      = form.prox_num.data or 1          # ← NOVO
            )
            db.session.add(novo)
            db.session.commit()
            flash("Usuário cadastrado com sucesso.", "success")
            return redirect(url_for("auth_bp.gerenciar_usuarios"))

    usuarios = User.query.all()
    return render_template("admin_usuarios.html", usuarios=usuarios, form=form)

# --------------------------------------------------------------------------- #
# Editar usuário – GET preenche modal | POST salva
# --------------------------------------------------------------------------- #
@auth_bp.route("/editar_usuario/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_usuario(id):
    usuario = User.query.get(id)
    if not usuario:
        return jsonify({"error": "Usuário não encontrado."}), 404

    if request.method == "POST":
        usuario.usuario       = request.form.get("usuario")
        usuario.nome_completo = request.form.get("nome_completo")
        usuario.email         = request.form.get("email")
        usuario.tipo          = request.form.get("tipo")
        usuario.prox_num      = int(request.form.get("prox_num") or usuario.prox_num)  # ← NOVO

        nova_senha = request.form.get("senha")
        if nova_senha:
            usuario.senha_hash = generate_password_hash(nova_senha)

        db.session.commit()
        return jsonify({"success": True})

    return jsonify({
        "id"          : usuario.id,
        "usuario"     : usuario.usuario,
        "nome_completo": usuario.nome_completo,
        "email"       : usuario.email,
        "tipo"        : usuario.tipo,
        "prox_num"    : usuario.prox_num               # ← NOVO
    })

# --------------------------------------------------------------------------- #
# Excluir usuário
# --------------------------------------------------------------------------- #
@auth_bp.route("/admin/usuarios/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_usuario(id):
    usuario = User.query.get_or_404(id)

    # evita que o usuário exclua a si mesmo
    if usuario.usuario == session.get("usuario"):
        flash("Você não pode excluir a si mesmo.", "danger")
        return redirect(url_for("auth_bp.gerenciar_usuarios"))

    db.session.delete(usuario)
    db.session.commit()
    flash("Usuário excluído com sucesso.", "success")
    return redirect(url_for("auth_bp.gerenciar_usuarios"))
