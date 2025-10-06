from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SelectField, SelectMultipleField,
    TextAreaField, SubmitField, IntegerField, BooleanField
)
from wtforms.validators import (
    DataRequired, NumberRange, Email, ValidationError, Optional
)
from flask_wtf.file import FileField, FileAllowed
from models import ParamCategory, ServicoType, ModalidadeType

# =========================
#  Validador e Função de CNPJ
# =========================

def cnpj_valido(cnpj):
    """Valida se um CNPJ é válido."""
    # Remove caracteres não numéricos
    cnpj = ''.join(filter(str.isdigit, cnpj or ''))
    if len(cnpj) != 14:
        return False
    # CNPJs com todos os dígitos iguais são inválidos
    if cnpj == cnpj[0] * 14:
        return False

    def calc_digit(cnpj_slice, multipliers):
        total = sum(int(d) * m for d, m in zip(cnpj_slice, multipliers))
        remainder = total % 11
        return '0' if remainder < 2 else str(11 - remainder)

    # Primeiro dígito verificador
    mult1 = [5,4,3,2,9,8,7,6,5,4,3,2]
    d1 = calc_digit(cnpj[:12], mult1)
    # Segundo dígito verificador
    mult2 = [6] + mult1
    d2 = calc_digit(cnpj[:12] + d1, mult2)

    return cnpj[-2:] == d1 + d2


def validar_cnpj(form, field):
    """WTForms validator para campo CNPJ."""
    if not cnpj_valido(field.data):
        raise ValidationError("CNPJ inválido.")

# =========================
#  Equipamentos Form
# =========================
class EquipmentForm(FlaskForm):
    name         = StringField('Nome', validators=[DataRequired()])
    description  = TextAreaField('Descrição')
    unit_price   = StringField('Preço Unitário')
    quantity     = StringField('Quantidade')
    illustration = FileField(
        'Imagem',
        validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Apenas imagens são permitidas')]
    )
    submit       = SubmitField('Salvar Equipamento')

# =========================
#  Proposals Form
# =========================
class ProposalForm(FlaskForm):
    company        = StringField('Empresa', validators=[DataRequired()])
    cnpj           = StringField('CNPJ do Cliente', validators=[DataRequired(), validar_cnpj])
    client_name    = StringField('Pessoa de Contato', validators=[DataRequired()])
    email          = StringField('E-mail', validators=[DataRequired(), Email(message="E-mail inválido")])
    telefone       = StringField('Telefone', validators=[DataRequired()])

    # Parâmetros dinamicamente preenchidos
    pagto_equip    = SelectField('Condições de Pagamento (Equipamento)', coerce=str)
    prazo_entrega  = SelectField('Prazo de Entrega', coerce=str)
    frete          = SelectField('Frete', coerce=str)
    validade       = SelectField('Validade da Proposta', coerce=str)
    garantia_eq    = SelectField('Garantia do Equipamento', coerce=str)
    garantia_sys   = SelectField('Garantia do Sistema', coerce=str)

    # Campos “Outros”
    pagto_equip_other   = StringField()
    prazo_entrega_other = StringField()
    frete_other         = StringField()
    validade_other      = StringField()
    garantia_eq_other   = StringField()
    garantia_sys_other  = StringField()

    equipments = SelectMultipleField('Equipamentos', coerce=int)

    # Proposta em nome de outro usuário
    usar_outro_usuario = SelectField(
        'Fazer proposta em nome de outro consultor?',
        choices=[('nao', 'Não'), ('sim', 'Sim')],
        default='nao',
        validators=[DataRequired()]
    )
    outro_usuario = SelectField('Selecione o Consultor', coerce=int, validate_choice=False)

    # Tipo de Serviço
    servico_type = SelectField(
        'Tipo de Serviço',
        choices=[(st.name, st.value) for st in ServicoType],
        validators=[DataRequired()],
        coerce=lambda v: ServicoType[v]
    )
    # Modalidade
    modalidade_type = SelectField(
        'Modalidade',
        choices=[(mt.name, mt.value) for mt in ModalidadeType],
        validators=[DataRequired()],
        coerce=lambda v: ModalidadeType[v]
    )

    enviar_email = BooleanField('Enviar e-mail para o cliente?')
    email_corpo = TextAreaField('Conteúdo do e-mail', validators=[Optional()])
    enviar_copia = BooleanField('Copiar outros e-mails?')
    email_cc = TextAreaField('E-mails em cópia', validators=[Optional()])

    submit         = SubmitField('Gerar Proposta')

# =========================
#  Usuários Form
# =========================
class UserForm(FlaskForm):
    usuario       = StringField('Usuário', validators=[DataRequired()])
    nome_completo = StringField('Nome Completo', validators=[DataRequired()])
    email         = StringField('E-mail')
    senha         = PasswordField('Senha', validators=[DataRequired()])
    tipo          = SelectField(
        'Tipo',
        choices=[('admin', 'Administrador'),('gestor', 'Gestor'),('usuario', 'Usuário')]
    )
    prox_num      = IntegerField('Próximo Nº de Proposta', default=1, validators=[NumberRange(min=1)])
    submit        = SubmitField('Cadastrar Usuário')

# =========================
#  Parâmetros da Proposta
# =========================
class ParamOptionForm(FlaskForm):
    category = SelectField(
        'Categoria',
        choices=[(c.name, c.name.replace('_', ' ').title()) for c in ParamCategory],
        coerce=lambda v: ParamCategory[v]
    )
    label    = StringField('Valor', validators=[DataRequired()])
    submit   = SubmitField('Salvar')
