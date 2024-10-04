"""changed constraints

Revision ID: feaa13fc4566
Revises: 7cc5e02c2bfb
Create Date: 2024-10-04 01:52:45.709771

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'feaa13fc4566'
down_revision = '7cc5e02c2bfb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('TransactionHistory', schema=None) as batch_op:
        batch_op.alter_column('sender',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=70),
               existing_nullable=False)
        batch_op.alter_column('receiver',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=70),
               existing_nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('TransactionHistory', schema=None) as batch_op:
        batch_op.alter_column('receiver',
               existing_type=sa.String(length=70),
               type_=sa.VARCHAR(length=20),
               existing_nullable=False)
        batch_op.alter_column('sender',
               existing_type=sa.String(length=70),
               type_=sa.VARCHAR(length=20),
               existing_nullable=False)

    # ### end Alembic commands ###
