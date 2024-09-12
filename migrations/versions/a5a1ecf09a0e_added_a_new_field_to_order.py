"""added a new field to order

Revision ID: a5a1ecf09a0e
Revises: 
Create Date: 2024-09-11 13:06:16.711218

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5a1ecf09a0e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('Order', schema=None) as batch_op:
        batch_op.add_column(sa.Column('date_product_delivered', sa.DateTime(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('Order', schema=None) as batch_op:
        batch_op.drop_column('date_product_delivered')

    # ### end Alembic commands ###