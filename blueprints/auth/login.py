"""Rotas de login e logout."""
from flask import (
    render_template, redirect, url_for,
    flash, request, session
)
from werkzeug.security import check_password_hash

from . import auth_bp         # Blueprint criado em __init__.py
from models import User


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario_form = request.form.get("usuario")
        senha_form   = request.form.get("senha")

        user = User.query.filter_by(usuario=usuario_form).first()
        if user and check_password_hash(user.senha_hash, senha_form):
            session.clear()                         # limpa qualquer resto
            session["usuario_id"] = user.id
            session["usuario"]    = user.usuario
            session["nome"]       = user.nome_completo
            session["tipo"]       = user.tipo
            session.permanent = True                # sessão até fechar browser
            flash("Login realizado com sucesso!", "success")
            # redireciona para URL desejada ou página inicial
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)

        flash("Usuário ou senha inválidos.", "danger")

    return render_template("auth/login.html")


# ------------------------------------------------------------------
# Logout
# ------------------------------------------------------------------
@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("auth_bp.login"))
