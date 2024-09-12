"""added 2 new columns

Revision ID: 96cad53db8bd
Revises: a5a1ecf09a0e
Create Date: 2024-09-11 13:18:26.993348

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '96cad53db8bd'
down_revision = 'a5a1ecf09a0e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('Order', schema=None) as batch_op:
        batch_op.add_column(sa.Column('extra_time_initiated', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('extra_time_elapsed', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('Order', schema=None) as batch_op:
        batch_op.drop_column('extra_time_elapsed')
        batch_op.drop_column('extra_time_initiated')

    # ### end Alembic commands ###
