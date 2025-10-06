"""add email fields to proposals

Revision ID: 6bff8c85f9f4
Revises: 3c29dcdd9497
Create Date: 2025-07-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6bff8c85f9f4'
down_revision = '3c29dcdd9497'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('enviar_email', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('email_corpo', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('email_cc', sa.Text(), nullable=True))

    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.alter_column('enviar_email', server_default=None)


def downgrade():
    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.drop_column('email_cc')
        batch_op.drop_column('email_corpo')
        batch_op.drop_column('enviar_email')
