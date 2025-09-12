"""add project title to groups

Revision ID: 882f7ea9cd22
Revises: 94851311a3b1
Create Date: 2025-08-14 12:41:13.221332

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '882f7ea9cd22'
down_revision = '94851311a3b1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tgi_groups', sa.Column('title', sa.String(length=200), nullable=True))
    op.execute("UPDATE tgi_groups SET title = CONCAT('Projeto #', id) WHERE title IS NULL")
    op.alter_column('tgi_groups', 'title', existing_type=sa.String(length=200), nullable=False)

def downgrade():
    op.drop_column('tgi_groups', 'title')

    # ### end Alembic commands ###
