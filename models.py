from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum

# Inicializa o SQLAlchemy
db = SQLAlchemy()

# Tabela de associação muitos-para-muitos entre Proposal e Equipment
proposal_equipments = db.Table(
    'proposal_equipments',
    db.Column('proposal_id', db.Integer, db.ForeignKey('proposals.id'), primary_key=True),
    db.Column('equipment_id', db.Integer, db.ForeignKey('equipments.id'), primary_key=True)
)

# ============================
#  Parametrização de Proposta
# ============================

class ParamCategory(Enum):
    PAGTO_EQUIP   = "pagto_equip"
    PRAZO_ENTREGA = "prazo_entrega"
    FRETE         = "frete"
    VALIDADE      = "validade"
    GARANTIA_EQ   = "garantia_eq"
    GARANTIA_SYS  = "garantia_sys"

class ParamOption(db.Model):
    __tablename__ = "param_options"
    __table_args__ = (
        db.UniqueConstraint("category", "label", name="uq_param_options_category_label"),
    )

    id            = db.Column(db.Integer, primary_key=True)
    category      = db.Column(db.Enum(ParamCategory), nullable=False)
    label         = db.Column(db.String(120), nullable=False)

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_by    = db.relationship(
        'User',
        backref='created_param_options'
    )

# ================
#  Usuários
# ================

class User(db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    usuario       = db.Column(db.String(64), unique=True, nullable=False)
    nome_completo = db.Column(db.String(128))
    senha_hash    = db.Column(db.String(200), nullable=False)
    tipo          = db.Column(db.String(20))    # admin | gestor | usuario
    email         = db.Column(db.String(128))

    prox_num      = db.Column(db.Integer, default=1)

    propostas = db.relationship('Proposal', backref='usuario', lazy=True)

# ================
#  Equipamentos
# ================

class Equipment(db.Model):
    __tablename__ = 'equipments'

    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(128))
    description      = db.Column(db.Text)
    illustration_path= db.Column(db.String(256))
    unit_price       = db.Column(db.Float)
    quantity         = db.Column(db.Integer)

# ================
#  Propostas
# ================

class ServicoType(Enum):
    PONTO   = "Ponto"
    ACESSO  = "Acesso"

class ModalidadeType(Enum):
    AQUISICAO = "Aquisição"
    LOCACAO   = "Locação"

class Proposal(db.Model):
    __tablename__ = 'proposals'

    id               = db.Column(db.Integer, primary_key=True)
    company          = db.Column(db.String(128))
    cnpj             = db.Column(db.String(32))
    client_name      = db.Column(db.String(128))
    email            = db.Column(db.String(128))
    telefone         = db.Column(db.String(32))

    pagamento        = db.Column(db.String(256))
    prazo_entrega    = db.Column(db.String(256))
    frete            = db.Column(db.String(256))
    validade         = db.Column(db.String(256))
    garantia         = db.Column(db.String(256))
    garantia_sistema = db.Column(db.String(256))
    
    servico_type    = db.Column(db.Enum(ServicoType), nullable=False, default=ServicoType.PONTO)
    modalidade_type = db.Column(db.Enum(ModalidadeType), nullable=False, default=ModalidadeType.AQUISICAO)

    data_criacao     = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    filename         = db.Column(db.String(128))

    # Relacionamento muitos-para-muitos com equipamentos
    equipamentos     = db.relationship('Equipment', secondary=proposal_equipments, backref='propostas', lazy='dynamic')
