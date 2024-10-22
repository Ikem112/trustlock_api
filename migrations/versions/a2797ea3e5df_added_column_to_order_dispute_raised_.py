"""added column to order - dispute raised date

Revision ID: a2797ea3e5df
Revises: 7fad5aaddf72
Create Date: 2024-10-12 21:14:27.016010

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2797ea3e5df'
down_revision = '7fad5aaddf72'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('Order', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dispute_raised_date', sa.DateTime(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('Order', schema=None) as batch_op:
        batch_op.drop_column('dispute_raised_date')

    # ### end Alembic commands ###