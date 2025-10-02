# blueprints/equipamentos/equipamentos.py
import os
import uuid
from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    jsonify,
)
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError

from . import equipamentos_bp
from blueprints.auth import login_required
from models import db, Equipment
from forms import EquipmentForm

# Configurações de imagem
ALLOWED_EXTS = {"png", "jpg", "jpeg", "webp"}
TARGET_W, TARGET_H = 160, 180
IMAGES_DIR = os.path.join("static", "images")


def _ensure_images_dir():
    os.makedirs(IMAGES_DIR, exist_ok=True)


def _save_image_letterbox(file_storage, filename_hint="eq"):
    """
    Valida a extensão, abre a imagem e a salva como PNG 160x180,
    usando letterbox (contain): sem cortes, centralizada e com
    preenchimento transparente (ou branco, se preferir).
    Retorna o caminho relativo "static/images/<arquivo>.png".
    """
    if not file_storage or not getattr(file_storage, "filename", ""):
        raise ValueError("Nenhuma imagem enviada.")

    # Extensão
    _, ext = os.path.splitext(file_storage.filename)
    ext = ext.lower().lstrip(".")
    if ext not in ALLOWED_EXTS:
        raise ValueError(
            "Formato de imagem não aceito. Use PNG, JPG, JPEG ou WEBP."
        )

    # Abre com Pillow
    try:
        img = Image.open(file_storage.stream)
    except UnidentifiedImageError:
        raise ValueError("Arquivo de imagem inválido ou corrompido.")

    # Converte para RGBA para manter transparência (se houver)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    # Redimensiona para CABER (contain), sem cortar
    img_copy = img.copy()
    img_copy.thumbnail((TARGET_W, TARGET_H), Image.LANCZOS)

    # Lona 160x180 — escolha o fundo:
    # fundo transparente:
    canvas = Image.new("RGBA", (TARGET_W, TARGET_H), (255, 255, 255, 0))
    # (se preferir branco: (255,255,255,255))

    # Centraliza
    off_x = (TARGET_W - img_copy.width) // 2
    off_y = (TARGET_H - img_copy.height) // 2
    canvas.paste(img_copy, (off_x, off_y), img_copy if img_copy.mode == "RGBA" else None)

    # Nome do arquivo final (PNG, compatível com Word/Docx)
    _ensure_images_dir()
    fname = f"{filename_hint}_{uuid.uuid4().hex}.png"
    rel_path = os.path.join("static", "images", fname)
    abs_path = os.path.join(IMAGES_DIR, fname)

    # Salva otimizado
    canvas.save(abs_path, format="PNG", optimize=True)
    return rel_path  # guardamos caminho relativo (resolvido no gerador)


# --------------------------------------------------------------------------- #
# Cadastro de equipamentos
# --------------------------------------------------------------------------- #
@equipamentos_bp.route("/cadastro_equipamentos", methods=["GET", "POST"])
@login_required
def cadastro_equipamentos():
    form = EquipmentForm()
    if form.validate_on_submit():
        # Processa imagem (opcional)
        illustration = form.illustration.data
        saved_path = None
        if illustration and getattr(illustration, "filename", ""):
            try:
                saved_path = _save_image_letterbox(illustration, filename_hint="eq")
            except ValueError as e:
                flash(str(e), "danger")
                # Mantém os dados preenchidos e não cria o registro
                equipamentos = Equipment.query.all()
                return render_template(
                    "cadastro_equipamentos.html",
                    equipments=equipamentos,
                    form=form,
                )

        # Preço
        preco_str = str(form.unit_price.data).replace(".", "").replace(",", ".")
        try:
            preco_float = float(preco_str)
        except ValueError:
            preco_float = 0.0

        eq = Equipment(
            name=form.name.data,
            description=form.description.data,
            unit_price=preco_float,
            quantity=int(form.quantity.data),
            illustration_path=saved_path,  # já relativo a static/images
        )
        db.session.add(eq)
        db.session.commit()
        flash("Equipamento cadastrado com sucesso.", "success")
        return redirect(url_for("equipamentos_bp.cadastro_equipamentos"))

    equipamentos = Equipment.query.all()
    return render_template(
        "cadastro_equipamentos.html",
        equipments=equipamentos,
        form=form,
    )


# --------------------------------------------------------------------------- #
# CRUD via AJAX / Lista
# --------------------------------------------------------------------------- #
@equipamentos_bp.route("/equipamentos/<int:id>", methods=["GET"])
@login_required
def get_equipamento(id):
    eq = Equipment.query.get_or_404(id)
    return jsonify(
        {
            "id": eq.id,
            "nome": eq.name,
            "descricao": eq.description,
            "imagem": eq.illustration_path or "",
            "preco": eq.unit_price,
            "quantidade": eq.quantity,
        }
    )


@equipamentos_bp.route("/equipamentos/<int:id>", methods=["POST"])
@login_required
def editar_equipamento(id):
    eq = Equipment.query.get_or_404(id)
    data = request.json or {}
    eq.name = data.get("nome", eq.name)
    eq.description = data.get("descricao", eq.description)

    preco_str = str(data.get("preco", eq.unit_price)).replace(".", "").replace(",", ".")
    try:
        eq.unit_price = float(preco_str)
    except ValueError:
        pass

    eq.quantity = int(data.get("quantidade", eq.quantity))
    db.session.commit()
    return jsonify({"success": True})


@equipamentos_bp.route("/equipamentos/<int:id>/upload_imagem", methods=["POST"])
@login_required
def upload_imagem_equipamento(id):
    eq = Equipment.query.get_or_404(id)
    imagem = request.files.get("imagem")
    if not imagem:
        return jsonify({"success": False, "error": "Nenhuma imagem enviada."}), 400

    try:
        new_rel_path = _save_image_letterbox(imagem, filename_hint=f"eq{id}")
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    # Remove a antiga (se estiver em static/images)
    old_rel = eq.illustration_path
    eq.illustration_path = new_rel_path
    db.session.commit()

    try:
        if old_rel and old_rel.startswith("static/images"):
            old_abs = os.path.join(os.getcwd(), old_rel)
            if os.path.exists(old_abs):
                os.remove(old_abs)
    except Exception:
        # falha de limpeza não deve quebrar o fluxo
        pass

    return jsonify({"success": True, "imagem": new_rel_path})


@equipamentos_bp.route("/equipamentos/<int:id>", methods=["DELETE"])
@login_required
def excluir_equipamento(id):
    eq = Equipment.query.get_or_404(id)

    # Apaga imagem associada
    try:
        if eq.illustration_path and eq.illustration_path.startswith("static/images"):
            abs_path = os.path.join(os.getcwd(), eq.illustration_path)
            if os.path.exists(abs_path):
                os.remove(abs_path)
    except Exception:
        pass

    db.session.delete(eq)
    db.session.commit()
    return jsonify({"success": True})
