"""
- Adds relationship between configs and organizations
- Adds relationship between users and organizations

Revision ID: 6bde57c7cbc3
Revises: 2e70e47d57e6
Create Date: 2020-03-21 08:14:35.248546

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6bde57c7cbc3'
down_revision = '2e70e47d57e6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('configurations', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'configurations', 'organizations', ['organization_id'], ['id'])
    op.add_column('users', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'users', 'organizations', ['organization_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'users', type_='foreignkey')
    op.drop_column('users', 'organization_id')
    op.drop_constraint(None, 'configurations', type_='foreignkey')
    op.drop_column('configurations', 'organization_id')
    # ### end Alembic commands ###
