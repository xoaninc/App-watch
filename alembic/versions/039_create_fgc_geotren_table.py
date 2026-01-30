"""Create FGC Geotren vehicle positions table.

Revision ID: 039
Revises: 038
Create Date: 2026-01-29

This table stores real-time train positions from FGC's Geotren service,
which includes occupancy data not available in standard GTFS-RT.

Source: https://dadesobertes.fgc.cat/explore/dataset/posicionament-dels-trens/
"""

from alembic import op
import sqlalchemy as sa


revision = '039'
down_revision = '038'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'fgc_geotren_positions',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('vehicle_id', sa.String(100), nullable=True),  # ut field - can be null for some trains
        sa.Column('line', sa.String(20)),  # lin field (S1, S2, L6, etc.)
        sa.Column('direction', sa.String(10)),  # dir field (D=down, A=up)
        sa.Column('origin', sa.String(50)),  # origen station code
        sa.Column('destination', sa.String(50)),  # desti station code
        sa.Column('next_stops', sa.Text()),  # properes_parades
        sa.Column('stationed_at', sa.String(50)),  # estacionat_a
        sa.Column('on_time', sa.Boolean()),  # en_hora
        sa.Column('unit_type', sa.String(50)),  # tipus_unitat (train model)
        sa.Column('latitude', sa.Float()),
        sa.Column('longitude', sa.Float()),
        # Occupancy fields - per car type
        # MI = middle car, RI = rear car, M1/M2 = motor cars
        sa.Column('occupancy_mi_percent', sa.Float()),
        sa.Column('occupancy_mi_level', sa.String(20)),  # tram = level (low/med/high)
        sa.Column('occupancy_ri_percent', sa.Float()),
        sa.Column('occupancy_ri_level', sa.String(20)),
        sa.Column('occupancy_m1_percent', sa.Float()),
        sa.Column('occupancy_m1_level', sa.String(20)),
        sa.Column('occupancy_m2_percent', sa.Float()),
        sa.Column('occupancy_m2_level', sa.String(20)),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Index for querying by line
    op.create_index('ix_fgc_geotren_line', 'fgc_geotren_positions', ['line'])

    # Index for querying by vehicle
    op.create_index('ix_fgc_geotren_vehicle', 'fgc_geotren_positions', ['vehicle_id'])


def downgrade():
    op.drop_index('ix_fgc_geotren_vehicle', table_name='fgc_geotren_positions')
    op.drop_index('ix_fgc_geotren_line', table_name='fgc_geotren_positions')
    op.drop_table('fgc_geotren_positions')
