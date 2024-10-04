"""new column to merchant

Revision ID: 3151578f8f61
Revises: feaa13fc4566
Create Date: 2024-10-04 03:01:43.482448

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3151578f8f61'
down_revision = 'feaa13fc4566'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('Merchant', schema=None) as batch_op:
        batch_op.add_column(sa.Column('account_creation_complete', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('Merchant', schema=None) as batch_op:
        batch_op.drop_column('account_creation_complete')

    # ### end Alembic commands ###
