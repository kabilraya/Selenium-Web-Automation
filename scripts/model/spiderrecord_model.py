from sqlalchemy import String, Column, Text, Integer
from sqlalchemy.orm import mapped_column, DeclarativeBase,Mapped

class Base(DeclarativeBase):
    pass

class SPIDERRECORD(Base):
    __tablename__ = "tbl_spiderrecord"

    srId: Mapped[int] = mapped_column(primary_key=True)
    moduleName: Mapped[str] = mapped_column(String(100), nullable=False)
    totalBid: Mapped[int] = mapped_column(Integer(), nullable=False)
    totalNewBid: Mapped[int] = mapped_column(Integer(), nullable=False)
    totalNewBidFile: Mapped[int] = mapped_column(Integer(), nullable=False)
    ecgain: Mapped[str] = mapped_column(String(45), nullable=False)
    timeElapsed: Mapped[str] = Column(Text, nullable=False)