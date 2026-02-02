"""add ai enrichment to alerts

Revision ID: 042
Revises: 041
Create Date: 2026-02-02 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '042'
down_revision = '041'
branch_labels = None
depends_on = None


def upgrade():
    """Add AI enrichment columns to gtfs_rt_alerts table."""
    # Add AI analysis columns (nullable to not break existing data)
    op.add_column('gtfs_rt_alerts', 
                  sa.Column('ai_severity', sa.String(50), nullable=True))
    op.add_column('gtfs_rt_alerts', 
                  sa.Column('ai_status', sa.String(50), nullable=True))
    op.add_column('gtfs_rt_alerts', 
                  sa.Column('ai_summary', sa.String(500), nullable=True))
    op.add_column('gtfs_rt_alerts', 
                  sa.Column('ai_affected_segments', sa.Text, nullable=True))
    op.add_column('gtfs_rt_alerts', 
                  sa.Column('ai_processed_at', sa.DateTime, nullable=True))
    
    # Index for filtering by severity
    op.create_index('ix_alerts_ai_severity', 'gtfs_rt_alerts', ['ai_severity'])


def downgrade():
    """Remove AI enrichment columns."""
    op.drop_index('ix_alerts_ai_severity', table_name='gtfs_rt_alerts')
    op.drop_column('gtfs_rt_alerts', 'ai_processed_at')
    op.drop_column('gtfs_rt_alerts', 'ai_affected_segments')
    op.drop_column('gtfs_rt_alerts', 'ai_summary')
    op.drop_column('gtfs_rt_alerts', 'ai_status')
    op.drop_column('gtfs_rt_alerts', 'ai_severity')
