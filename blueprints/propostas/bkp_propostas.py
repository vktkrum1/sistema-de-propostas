# blueprints/propostas/propostas.py
# ===========================================================
#  IMPORTS E CONFIGURAÇÃO GERAL
# ===========================================================
from datetime import datetime, timezone

from flask import (
    render_template, redirect, url_for, flash,
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
from utils.timezone import get_local_timezone
import dns.resolver

LOCAL_TZ = get_local_timezone()

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


def _gerar_e_enviar_pdf(proposta, equipamentos):
    nome_colab, email_colab = _dados_colaborador()
    cod = proposta.filename.split()[-1]
    output = gerar_proposta_docx(
        proposta, equipamentos,
        formato="pdf",
        nome_colaborador=nome_colab,
        email_colaborador=email_colab,
        proposta_cod=cod,
    )
    return send_file(
        output,
        download_name=f"{proposta.filename}.pdf",
        as_attachment=False,
    )

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

        proposta = Proposal(
            company=form.company.data,
            cnpj=form.cnpj.data,
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
        )
        db.session.add(proposta)
        db.session.commit()

        # Equipamentos escolhidos
        eqs, descontos, precos = [], {}, {}
        for eid in request.form.getlist("equipments"):
            eq = Equipment.query.get(int(eid))
            if not eq:
                continue
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

        # Buffers em sessão
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
#  Demais rotas (baixar / visualizar / editar / excluir / histórico)
#  — permanecem exatamente como estavam na versão anterior —
# ===========================================================
# ... (mantenha o restante do arquivo, não houve mudanças além da indentação)


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
    eqs = _preparar_equipamentos_para_proposta()
    resp = _gerar_e_enviar_pdf(prop, eqs)

    # Força download
    resp.headers["Content-Disposition"] = f'attachment; filename="{prop.filename}.pdf"'

    # Limpa buffers
    for k in (
        "ultima_proposta_id",
        "equipamentos_buffer",
        "quantidades_buffer",
        "descontos_buffer",
        "precos_buffer",
    ):
        session.pop(k, None)
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
    for k in (
        "ultima_proposta_id",
        "equipamentos_buffer",
        "quantidades_buffer",
        "descontos_buffer",
        "precos_buffer",
    ):
        session.pop(k, None)
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

    # Para download direto sempre geramos PDF do zero
    eqs = _preparar_equipamentos_para_proposta() if session.get("ultima_proposta_id") == id else Equipment.query.all()
    return _gerar_e_enviar_pdf(prop, eqs)


@propostas_bp.route("/editar_proposta/<int:id>", methods=["GET", "POST"])
@login_required
def editar_proposta(id):
    prop = Proposal.query.get_or_404(id)
    if session.get("tipo") not in ["admin", "gestor"] and prop.usuario_id != session.get("usuario_id"):
        return jsonify({"error": "Acesso não autorizado."}), 403

    if request.method == "POST":
        # --- Validação de CNPJ ---
        cnpj = request.form.get("cnpj", "")
        cnpj_num = "".join(filter(str.isdigit, cnpj))
        if len(cnpj_num) != 14 or not cnpj_valido(cnpj_num):
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
        ]:
            valor = request.form.get(campo)
            if campo == "servico_type" and valor:
                valor = ServicoType[valor]
            if campo == "modalidade_type" and valor:
                valor = ModalidadeType[valor]
            setattr(prop, campo, valor)

        # --- Equipamentos ---
        prop.equipamentos.clear()
        eqs, descontos, precos = [], {}, {}
        for eid in request.form.getlist("equipments"):
            eq = Equipment.query.get(int(eid))
            if not eq:
                continue
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
        for eq in prop.equipamentos
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
    )
