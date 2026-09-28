"""create table wishlist"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f32565cc479d'
down_revision: Union[str, None] = 'e152518754cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('wishlists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'product_id', name='unique_user_product_wishlist')
    )
    op.create_index(op.f('ix_wishlists_product_id'), 'wishlists', ['product_id'], unique=False)
    op.create_index(op.f('ix_wishlists_user_id'), 'wishlists', ['user_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_wishlists_product_id'), table_name='wishlists')
    op.drop_index(op.f('ix_wishlists_user_id'), table_name='wishlists')
    op.drop_table('wishlists')