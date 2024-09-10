"""increased size of varchar

Revision ID: e9dae5827d15
Revises: 9bbdf6f8f06c
Create Date: 2024-09-06 17:00:10.973504

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9dae5827d15'
down_revision = '9bbdf6f8f06c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('Customer', schema=None) as batch_op:
        batch_op.alter_column('email_address',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=50),
               existing_nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('Customer', schema=None) as batch_op:
        batch_op.alter_column('email_address',
               existing_type=sa.String(length=50),
               type_=sa.VARCHAR(length=20),
               existing_nullable=False)

    # ### end Alembic commands ###