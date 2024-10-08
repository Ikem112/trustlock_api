"""added column to order details

Revision ID: 9468ee82b528
Revises: 0b9d00a8930a
Create Date: 2024-09-30 20:16:57.208885

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9468ee82b528'
down_revision = '0b9d00a8930a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('order_details', schema=None) as batch_op:
        batch_op.add_column(sa.Column('order_feedback', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('order_details', schema=None) as batch_op:
        batch_op.drop_column('order_feedback')

    # ### end Alembic commands ###
