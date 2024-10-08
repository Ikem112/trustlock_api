"""added foreign key to delivery information

Revision ID: f3cfa90b960a
Revises: ab4a423578fe
Create Date: 2024-09-27 18:27:56.779988

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3cfa90b960a'
down_revision = 'ab4a423578fe'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('DeliveryInformation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('order_id', sa.String(length=50), nullable=True))
        batch_op.create_foreign_key(None, 'Order', ['order_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('DeliveryInformation', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('order_id')

    # ### end Alembic commands ###
