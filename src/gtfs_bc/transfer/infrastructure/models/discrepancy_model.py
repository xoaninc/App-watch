from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime
from sqlalchemy.sql import func
from core.base import Base


class CorrespondenceDiscrepancyModel(Base):
    """Model to store discrepancies found during import for manual review.

    When importing correspondence data from CSV, if the value in the database
    differs from the value in the CSV, we store the discrepancy here instead
    of overwriting. This allows manual review and resolution.
    """
    __tablename__ = "correspondence_discrepancies"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Which stop has the discrepancy
    stop_id = Column(String(100), nullable=False, index=True)
    stop_name = Column(String(255), nullable=True)

    # Which field has the discrepancy (cor_metro, cor_cercanias, cor_ml, cor_tranvia)
    field = Column(String(50), nullable=False)

    # The values that differ
    value_in_db = Column(Text, nullable=True)
    value_in_csv = Column(Text, nullable=True)

    # Type of discrepancy
    # - 'missing_in_db': CSV has lines that DB doesn't have
    # - 'missing_in_csv': DB has lines that CSV doesn't have
    # - 'different': Both have values but they're different
    discrepancy_type = Column(String(50), nullable=True)

    # Review status
    reviewed = Column(Boolean, default=False, index=True)

    # Resolution chosen after review
    # - 'keep_db': Keep the database value
    # - 'use_csv': Use the CSV value
    # - 'manual': Manually set a different value
    resolution = Column(String(50), nullable=True)

    # Notes from reviewer
    notes = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Discrepancy {self.stop_id}.{self.field}: DB='{self.value_in_db}' vs CSV='{self.value_in_csv}'>"
