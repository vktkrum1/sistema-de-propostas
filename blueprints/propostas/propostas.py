# blueprints/propostas/propostas.py
# ===========================================================
#  IMPORTS E CONFIGURAÇÃO GERAL
# ===========================================================
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from email.message import EmailMessage
import re
import smtplib
from typing import Sequence

from flask import (
    current_app, render_template, redirect, url_for, flash,
    request, session, jsonify, send_file
)

from . import propostas_bp
from blueprints.auth import login_required
from models import (
    db, Equipment, Proposal, User,
    ParamOption, ParamCategory,
    ServicoType, ModalidadeType
)
from forms import ProposalForm, cnpj_valido
from gerar_proposta import gerar_proposta_docx
import dns.resolver

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")

# ===========================================================
#  HELPERS
# ===========================================================
def email_domain_has_mx(email: str) -> bool:
    try:
        domain = email.split("@")[-1]
        dns.resolver.resolve(domain, "MX")
        return True
    except Exception:
        return False


def _usuario_atual():
    uid = session.get("usuario_id")
    return User.query.get(uid) if uid else None


def _preparar_equipamentos_para_proposta():
    ids       = session.get("equipamentos_buffer", [])
    quantias  = session.get("quantidades_buffer", {})
    descontos = session.get("descontos_buffer", {})
    precos    = session.get("precos_buffer", {})

    lista = []
    for eid in ids:
        eq = Equipment.query.get(eid)
        if not eq:
            continue
        eq.quantity         = int(quantias.get(str(eid), 1))
        eq.discount_percent = float(descontos.get(str(eid), 0))
        eq.unit_price       = float(precos.get(str(eid), eq.unit_price))
        lista.append(eq)
    return lista


def _dados_colaborador():
    pid  = session.get("ultima_proposta_id")
    prop = Proposal.query.get(pid)
    if not prop:
        return "", ""
    usr = User.query.get(prop.usuario_id)
    return usr.nome_completo or "", usr.email or ""


def _limpar_buffers_proposta():
    for chave in (
        "ultima_proposta_id",
        "equipamentos_buffer",
        "quantidades_buffer",
        "descontos_buffer",
        "precos_buffer",
    ):
        session.pop(chave, None)


def _fill_selects(form: ProposalForm):
    def opts(cat):
        res = [("", "-- Selecione --")]
        res += [(o.label, o.label) for o in
                ParamOption.query.filter_by(category=cat)
                                 .order_by(ParamOption.label)]
        res.append(("outros", "Outros"))
        return res

    form.pagto_equip.choices   = opts(ParamCategory.PAGTO_EQUIP)
    form.prazo_entrega.choices = opts(ParamCategory.PRAZO_ENTREGA)
    form.frete.choices         = opts(ParamCategory.FRETE)
    form.validade.choices      = opts(ParamCategory.VALIDADE)
    form.garantia_eq.choices   = opts(ParamCategory.GARANTIA_EQ)
    form.garantia_sys.choices  = opts(ParamCategory.GARANTIA_SYS)


def _gerar_pdf_stream(proposta, equipamentos):
    nome_colab, email_colab = _dados_colaborador()
    cod = proposta.filename.split()[-1]
    return gerar_proposta_docx(
        proposta, equipamentos,
        formato="pdf",
        nome_colaborador=nome_colab,
        email_colaborador=email_colab,
        proposta_cod=cod,
    )


def _gerar_e_enviar_pdf(proposta, equipamentos):
    output = _gerar_pdf_stream(proposta, equipamentos)
    return send_file(
        output,
        download_name=f"{proposta.filename}.pdf",
        as_attachment=False,
    )


EMAIL_SPLIT_RE = re.compile(r"[;,\n]+")


def _parse_emails_list(raw: str) -> list[str]:
    if not raw:
        return []
    emails: list[str] = []
    for chunk in EMAIL_SPLIT_RE.split(raw):
        addr = chunk.strip()
        if not addr:
            continue
        if "@" not in addr or addr.startswith("@") or addr.endswith("@"):
            raise ValueError(f"E-mail inválido: {addr}")
        local, _, domain = addr.partition("@")
        if not local or "." not in domain:
            raise ValueError(f"E-mail inválido: {addr}")
        emails.append(addr)
    return emails


def _enviar_email_proposta(
    proposta: Proposal,
    equipamentos: Sequence[Equipment],
    corpo_email: str,
    cc_list: Sequence[str],
):
    config = current_app.config
    host = config.get("MAIL_SERVER") or config.get("EMAIL_SMTP_SERVER")
    if not host:
        raise RuntimeError("Configuração MAIL_SERVER ausente para envio de e-mail.")

    sender = config.get("MAIL_SENDER") or config.get("MAIL_DEFAULT_SENDER")
    if not sender:
        raise RuntimeError("Configuração MAIL_SENDER ausente para envio de e-mail.")

    use_ssl = bool(config.get("MAIL_USE_SSL", False))
    use_tls = bool(config.get("MAIL_USE_TLS", not use_ssl))
    port = config.get("MAIL_PORT")
    if not port:
        port = 465 if use_ssl else (587 if use_tls else 25)

    username = config.get("MAIL_USERNAME")
    password = config.get("MAIL_PASSWORD")

    pdf_stream = _gerar_pdf_stream(proposta, equipamentos)
    pdf_stream.seek(0)
    attachment = pdf_stream.read()

    msg = EmailMessage()
    msg["Subject"] = proposta.filename or "Proposta Comercial"
    msg["From"] = sender
    msg["To"] = proposta.email
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    reply_to = config.get("MAIL_REPLY_TO")
    if reply_to:
        msg["Reply-To"] = reply_to

    corpo = corpo_email.strip() or (
        f"Olá {proposta.client_name},\n\n"
        "Segue em anexo a proposta comercial referente ao nosso atendimento.\n\n"
        "Fico à disposição para dúvidas."
    )
    msg.set_content(corpo)

    msg.add_attachment(
        attachment,
        maintype="application",
        subtype="pdf",
        filename=f"{proposta.filename}.pdf",
    )

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port)
    else:
        server = smtplib.SMTP(host, port)

    try:
        if use_tls and not use_ssl:
            server.starttls()
        if username:
            server.login(username, password or "")
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass

# ===========================================================
#  NOVA PROPOSTA
# ===========================================================
@propostas_bp.route("/nova_proposta", methods=["GET", "POST"])
@login_required
def nova_proposta():                    # ← NENHUM espaço antes desta linha
    form = ProposalForm()
    _fill_selects(form)

    equipamentos_disp = Equipment.query.all()
    form.equipments.choices = [(e.id, e.name) for e in equipamentos_disp]

    usuario_logado = _usuario_atual()
    outros = (User.query
              .filter(User.id != usuario_logado.id, User.tipo != "admin")
              .order_by(User.nome_completo).all())
    form.outro_usuario.choices = [(u.id, u.nome_completo) for u in outros]

    # ------------------------------------------------------------------
    #  POST
    # ------------------------------------------------------------------
    if form.validate_on_submit():
        # Validação rápida do domínio de e-mail
        email = form.email.data.strip()
        if not email_domain_has_mx(email):
            flash("Domínio de e-mail sem registro MX.", "danger")
            return render_template(
                "nova_proposta.html",
                form=form,
                equipments=equipamentos_disp,
                form_data=request.form,
            )

        enviar_email = form.enviar_email.data
        corpo_email = (form.email_corpo.data or "").strip()
        enviar_copia = form.enviar_copia.data
        cc_raw = (form.email_cc.data or "").strip() if enviar_copia else ""

        if enviar_email and not corpo_email:
            flash("Informe o conteúdo do e-mail para enviá-lo ao cliente.", "danger")
            return render_template(
                "nova_proposta.html",
                form=form,
                equipments=equipamentos_disp,
                form_data=request.form,
            )

        try:
            cc_list = _parse_emails_list(cc_raw) if enviar_email else []
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template(
                "nova_proposta.html",
                form=form,
                equipments=equipamentos_disp,
                form_data=request.form,
            )

        # Usuário responsável
        user = usuario_logado
        if form.usar_outro_usuario.data == "sim":
            user = User.query.get(form.outro_usuario.data) or user

        # Nome do arquivo
        nomes = user.nome_completo.strip().split()
        iniciais = (nomes[0][0] + (nomes[-1][0] if len(nomes) > 1 else "")).upper()
        if not iniciais:
            iniciais = user.usuario[:2].upper()

        numero = user.prox_num or 1
        user.prox_num = numero + 1
        db.session.commit()
        filename = f"PROPOSTA COMERCIAL {iniciais}{numero:02d}"

        # Helper para selects “outros”
        sel = lambda campo, outro: outro.data.strip() if campo.data == "outros" else campo.data or ""

        # Cria a proposta
        proposta = Proposal(
            company=form.company.data,
            cnpj=form.cnpj.data,  # CNPJ opcional
            client_name=form.client_name.data,
            email=email,
            telefone=form.telefone.data,
            pagamento=sel(form.pagto_equip, form.pagto_equip_other),
            prazo_entrega=sel(form.prazo_entrega, form.prazo_entrega_other),
            frete=sel(form.frete, form.frete_other),
            validade=sel(form.validade, form.validade_other),
            garantia=sel(form.garantia_eq, form.garantia_eq_other),
            garantia_sistema=sel(form.garantia_sys, form.garantia_sys_other),
            servico_type=form.servico_type.data,
            modalidade_type=form.modalidade_type.data,
            usuario_id=user.id,
            filename=filename,
            enviar_email=enviar_email,
            email_corpo=corpo_email if enviar_email else "",
            email_cc=cc_raw if enviar_email else "",
        )
        db.session.add(proposta)
        db.session.commit()  # garante ID para usar nos buffers

        # ----------------------------------------------------------
        # Equipamentos escolhidos — ANEXA AO RELACIONAMENTO
        # ----------------------------------------------------------
        eqs, descontos, precos = [], {}, {}
        for eid in request.form.getlist("equipments"):
            eq = Equipment.query.get(int(eid))
            if not eq:
                continue

            # Atributos efêmeros para a geração imediata do PDF
            eq.quantity = int(request.form.get(f"quantity_{eid}", 1))
            pct = float(request.form.get(f"discount_{eid}", "0") or 0)
            eq.discount_percent = pct
            descontos[str(eid)] = pct

            ps = request.form.get(f"price_{eid}", "").strip()
            if ps:
                try:
                    eq.unit_price = float(ps.replace(".", "").replace(",", "."))
                except ValueError:
                    pass
            precos[str(eid)] = eq.unit_price

            eqs.append(eq)
            # vínculo persistente na tabela de associação
            proposta.equipamentos.append(eq)

        db.session.commit()  # salva os vínculos proposta ⇆ equipamentos

        # Buffers em sessão (para baixar/visualizar logo após criar)
        session.update(
            ultima_proposta_id=proposta.id,
            equipamentos_buffer=[e.id for e in eqs],
            quantidades_buffer={str(e.id): e.quantity for e in eqs},
            descontos_buffer=descontos,
            precos_buffer=precos,
        )

        acao = request.form.get("acao")
        if acao == "baixar":
            return redirect(url_for("propostas_bp.baixar_proposta"))
        if acao == "visualizar":
            return redirect(url_for("propostas_bp.visualizar_proposta"))
        if acao == "enviar_email" and enviar_email:
            try:
                _enviar_email_proposta(proposta, eqs, corpo_email, cc_list)
            except Exception as exc:
                current_app.logger.exception("Falha ao enviar e-mail da proposta")
                flash(f"Não foi possível enviar o e-mail: {exc}", "danger")
                return render_template(
                    "nova_proposta.html",
                    form=form,
                    equipments=equipamentos_disp,
                    form_data=request.form,
                )
            _limpar_buffers_proposta()
            flash("Proposta enviada por e-mail com sucesso.", "success")
            return redirect(url_for("propostas_bp.nova_proposta"))

        flash("Proposta criada com sucesso.", "success")
        return redirect(url_for("propostas_bp.nova_proposta"))

    # ------------------------------------------------------------------
    #  GET
    # ------------------------------------------------------------------
    return render_template(
        "nova_proposta.html",
        form=form,
        equipments=equipamentos_disp,
        form_data=request.form,
    )

# ===========================================================
#  BAIXAR / VISUALIZAR
# ===========================================================
@propostas_bp.route("/baixar_proposta")
@login_required
def baixar_proposta():
    pid = session.get("ultima_proposta_id")
    if not pid:
        flash("Nenhuma proposta para baixar.", "warning")
        return redirect(url_for("propostas_bp.nova_proposta"))

    prop = Proposal.query.get_or_404(pid)
    # Usa os buffers (acabou de criar) — contém qty/discount/price temporários
    eqs = _preparar_equipamentos_para_proposta()
    resp = _gerar_e_enviar_pdf(prop, eqs)

    # Força download
    resp.headers["Content-Disposition"] = f'attachment; filename="{prop.filename}.pdf"'

    # Limpa buffers
    _limpar_buffers_proposta()
    return resp


@propostas_bp.route("/visualizar_proposta")
@login_required
def visualizar_proposta():
    pid = session.get("ultima_proposta_id")
    if not pid:
        flash("Nenhuma proposta para visualizar.", "warning")
        return redirect(url_for("propostas_bp.nova_proposta"))

    prop = Proposal.query.get_or_404(pid)
    eqs = _preparar_equipamentos_para_proposta()
    resp = _gerar_e_enviar_pdf(prop, eqs)

    # Limpa buffers
    _limpar_buffers_proposta()
    return resp

# ===========================================================
#  DOWNLOAD / EDITAR / EXCLUIR / HISTÓRICO
# ===========================================================
@propostas_bp.route("/download_proposta/<int:id>")
@login_required
def download_proposta(id):
    prop = Proposal.query.get_or_404(id)
    if session.get("tipo") not in ["admin", "gestor"] and prop.usuario_id != session.get("usuario_id"):
        flash("Sem permissão.", "danger")
        return redirect(url_for("propostas_bp.historico_propostas"))

    # do histórico, use APENAS os itens vinculados à proposta
    eqs = prop.equipamentos.all()

    # Fallbacks para atributos esperados pelo gerador
    for e in eqs:
        if not hasattr(e, "quantity") or e.quantity in (None, 0):
            e.quantity = 1
        if not hasattr(e, "discount_percent") or e.discount_percent is None:
            e.discount_percent = 0.0

    return _gerar_e_enviar_pdf(prop, eqs)


@propostas_bp.route("/editar_proposta/<int:id>", methods=["GET", "POST"])
@login_required
def editar_proposta(id):
    prop = Proposal.query.get_or_404(id)
    if session.get("tipo") not in ["admin", "gestor"] and prop.usuario_id != session.get("usuario_id"):
        return jsonify({"error": "Acesso não autorizado."}), 403

    if request.method == "POST":
        # --- Validação de CNPJ (opcional) ---
        cnpj = request.form.get("cnpj", "")
        cnpj_num = "".join(filter(str.isdigit, cnpj))
        if cnpj_num and (len(cnpj_num) != 14 or not cnpj_valido(cnpj_num)):
            return jsonify({"error": "CNPJ inválido."}), 400

        # --- Campos simples ---
        for campo in [
            "company",
            "cnpj",
            "client_name",
            "email",
            "telefone",
            "pagamento",
            "prazo_entrega",
            "frete",
            "validade",
            "garantia",
            "garantia_sistema",
            "servico_type",
            "modalidade_type",
            "enviar_email",
            "email_corpo",
            "email_cc",
        ]:
            valor = request.form.get(campo)
            if campo == "servico_type" and valor:
                valor = ServicoType[valor]
            elif campo == "modalidade_type" and valor:
                valor = ModalidadeType[valor]
            elif campo == "enviar_email":
                valor = valor in {"1", "true", "on", "yes"}
            elif campo in {"email_corpo", "email_cc"} and valor is not None:
                valor = valor.strip()
            setattr(prop, campo, valor)

        # --- Equipamentos: recria vínculos (sem usar .clear()) ---
        for eq_old in prop.equipamentos.all():
            prop.equipamentos.remove(eq_old)

        for eid in request.form.getlist("equipments"):
            eq = Equipment.query.get(int(eid))
            if not eq:
                continue
            # atributos efêmeros usados para PDF eventual imediato
            eq.quantity = int(request.form.get(f"quantity_{eid}", 1))
            pct = float(request.form.get(f"discount_{eid}", "0") or 0)
            eq.discount_percent = pct
            ps = request.form.get(f"price_{eid}", "").strip()
            if ps:
                try:
                    eq.unit_price = float(ps.replace(".", "").replace(",", "."))
                except ValueError:
                    pass
            prop.equipamentos.append(eq)

        db.session.commit()
        return jsonify({"success": True})

    # --- GET → retorna JSON ---
    eq_list = [
        {
            "id": eq.id,
            "name": eq.name,
            "quantity": getattr(eq, "quantity", 1),
            "discount_percent": getattr(eq, "discount_percent", 0),
            "unit_price": getattr(eq, "unit_price", 0),
        }
        for eq in prop.equipamentos.all()
    ]
    return jsonify(
        proposta_id=prop.id,
        company=prop.company,
        cnpj=prop.cnpj,
        client_name=prop.client_name,
        email=prop.email,
        telefone=prop.telefone,
        pagamento=prop.pagamento,
        prazo_entrega=prop.prazo_entrega,
        frete=prop.frete,
        validade=prop.validade,
        garantia=prop.garantia,
        garantia_sistema=prop.garantia_sistema,
        servico_type=prop.servico_type.name if prop.servico_type else "",
        modalidade_type=prop.modalidade_type.name if prop.modalidade_type else "",
        enviar_email=prop.enviar_email,
        email_corpo=prop.email_corpo,
        email_cc=prop.email_cc,
        equipamentos=eq_list,
    )


@propostas_bp.route("/excluir_proposta/<int:id>", methods=["POST"])
@login_required
def excluir_proposta(id):
    if session.get("tipo") not in ["admin", "gestor"]:
        return jsonify({"error": "Acesso negado"}), 403

    prop = Proposal.query.get_or_404(id)
    db.session.delete(prop)
    db.session.commit()

    flash("Proposta excluída com sucesso.", "info")
    return redirect(url_for("propostas_bp.historico_propostas"))


@propostas_bp.route("/historico_propostas")
@login_required
def historico_propostas():
    tipo = session.get("tipo")
    data_filter = request.args.get("data")
    page = request.args.get("page", 1, type=int)
    serv_filter = request.args.get("servico_type")
    mod_filter = request.args.get("modalidade_type")
    user_filter = request.args.get("usuario_id", type=int)

    q = Proposal.query
    if tipo not in ["admin", "gestor"]:
        q = q.filter_by(usuario_id=session.get("usuario_id"))

    if data_filter:
        try:
            dia = datetime.strptime(data_filter, "%Y-%m-%d").date()
            q = q.filter(db.func.date(Proposal.data_criacao) == dia)
        except ValueError:
            flash("Data inválida.", "warning")

    if user_filter:
        q = q.filter_by(usuario_id=user_filter)
    if serv_filter:
        q = q.filter_by(servico_type=ServicoType[serv_filter])
    if mod_filter:
        q = q.filter_by(modalidade_type=ModalidadeType[mod_filter])

    propostas = q.order_by(Proposal.data_criacao.desc()).paginate(page=page, per_page=10)

    # Ajuste de fuso horário
    for p in propostas.items:
        if p.data_criacao:
            if p.data_criacao.tzinfo is None:
                p.data_criacao = p.data_criacao.replace(tzinfo=timezone.utc)
            p.data_criacao = p.data_criacao.astimezone(LOCAL_TZ)
            p.data_criacao_local = p.data_criacao

    usuarios = (
        User.query.filter(User.tipo != "admin").order_by(User.nome_completo).all()
    )

    # >>> envia a lista de equipamentos para o modal de edição
    equipamentos_disp = Equipment.query.order_by(Equipment.name).all()

    return render_template(
        "historico_propostas.html",
        propostas=propostas,
        usuarios_list=usuarios,
        servico_sel=serv_filter,
        modalidade_sel=mod_filter,
        user_sel=user_filter,
        date_sel=data_filter,
        ServicoType=ServicoType,
        ModalidadeType=ModalidadeType,
        ParamOption=ParamOption,
        ParamCategory=ParamCategory,
        equipments=equipamentos_disp,  # <<< necessário para popular o <select> do modal
    )
