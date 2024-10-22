"""added column to product_return

Revision ID: 39b2fd0729e2
Revises: 7b1edbc2497f
Create Date: 2024-10-20 01:13:44.160726

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '39b2fd0729e2'
down_revision = '7b1edbc2497f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('ProductReturn', schema=None) as batch_op:
        batch_op.add_column(sa.Column('date_returned_product_inspection_time_triggered', sa.DateTime(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('ProductReturn', schema=None) as batch_op:
        batch_op.drop_column('date_returned_product_inspection_time_triggered')

    # ### end Alembic commands ###
