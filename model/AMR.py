from sqlalchemy import String, Column, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column,DeclarativeBase

class Base(DeclarativeBase):
    pass

class AMR(Base):
    __tablename__ = "tbl_bid_info"

    id: Mapped[int] = mapped_column(primary_key=True)
    agency_ecgain: Mapped[str] = mapped_column(String(25), nullable=True)
    number: Mapped[str] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    brodcast_date: Mapped[str] = mapped_column(String(50), nullable=True)
    due_date: Mapped[str] = mapped_column(String(50), nullable=True)
    hash_value: Mapped[str] = mapped_column(String(1000), nullable=True)
    url1: Mapped[str] = mapped_column(String(500), nullable=True)
    url2: Mapped[str] = mapped_column(String(500), nullable=True)