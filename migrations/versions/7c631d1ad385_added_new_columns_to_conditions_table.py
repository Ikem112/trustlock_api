"""added new columns to conditions table

Revision ID: 7c631d1ad385
Revises: fc86e7f654fa
Create Date: 2024-09-27 01:33:21.330686

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c631d1ad385'
down_revision = 'fc86e7f654fa'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('TransactionCondition', schema=None) as batch_op:
        batch_op.add_column(sa.Column('partial_disburse_requisite', sa.Boolean(), nullable=False))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('TransactionCondition', schema=None) as batch_op:
        batch_op.drop_column('partial_disburse_requisite')

    # ### end Alembic commands ###