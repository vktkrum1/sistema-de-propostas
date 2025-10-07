"""add system fields to proposals"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1a9c7fa3a63'
down_revision = '6bff8c85f9f4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('proposals') as batch_op:
        batch_op.add_column(sa.Column('sistema_ativo', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('sistema_nome', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('sistema_descricao', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('sistema_imagem', sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column('sistema_quantidade', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sistema_preco_unitario', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('sistema_preco_total', sa.Float(), nullable=True))

    with op.batch_alter_table('proposals') as batch_op:
        batch_op.alter_column('sistema_ativo', server_default=None)


def downgrade():
    with op.batch_alter_table('proposals') as batch_op:
        batch_op.drop_column('sistema_preco_total')
        batch_op.drop_column('sistema_preco_unitario')
        batch_op.drop_column('sistema_quantidade')
        batch_op.drop_column('sistema_imagem')
        batch_op.drop_column('sistema_descricao')
        batch_op.drop_column('sistema_nome')
        batch_op.drop_column('sistema_ativo')
