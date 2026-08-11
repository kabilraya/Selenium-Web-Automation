from sqlalchemy import String, Column, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column,DeclarativeBase

class Base(DeclarativeBase):
    pass

class SMI(Base):
    __tablename__ = "tbl_WebBid"

    #this is the schema for the table tbl_WebBid

    WebID : Mapped[int] = mapped_column(primary_key=True)
    #Here the mapped_column() automatically maps the python data structure (i.e. int to the database appropriate datatype)
    stHash : Mapped[str] = mapped_column(Text, nullable=False)
    ECGAINS : Mapped[str] = Column(String(50),nullable=False)
    #Column() is the old ORM method which cannot automatically map the python datatype into the db
    stBidNo : Mapped[str] = mapped_column(String(100), nullable=False)
    stTitle : Mapped[str] = mapped_column(String(250), nullable=False)
    txtDescription: Mapped[str] = mapped_column(String(250),nullable=False)
    stdDueDate : Mapped[str] = mapped_column(String(100),nullable=False)
    stURL1 : Mapped[str] = mapped_column(Text, nullable=False)
    stURL2 : Mapped[str] = mapped_column(Text, nullable=False)
    stModuleName : Mapped[str] = mapped_column(String(100), nullable=False)
    stFileName : Mapped[str] = mapped_column(String(200), nullable=False)
    iConverted: Mapped[int] = mapped_column(nullable=False)
    stFileSize : Mapped[str] = mapped_column(String(50),nullable = False)
    stBidType: Mapped[str] = mapped_column(String(25), nullable=False, default="NPL")
