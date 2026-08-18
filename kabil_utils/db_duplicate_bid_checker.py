from sqlalchemy.sql import exists
import sys
import os
from sqlalchemy.orm import Session
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from model.smi_model import SMI

def check_duplicate_bids(session: Session, bid_no: str) -> bool:
    """Checks if there are any records that has the stBidNo as same as the bid_no

    Args:
        session (Session): Existing session of the database
        bid_no (str): bid_no of the current bid that is being inserted

    Returns:
        bool: True if duplicate bid_no exists, False if no same bid_no
    """

    return session.query(exists().where(SMI.stBidNo == bid_no)).scalar()
    # Breaking down the SQLAlchemy ORM session.query
    # Here session.query gets an exists() which is another function like filter()
    #SMI.stBidNo == bid_no is the mapping of python native data into ORM model.
    #in database it corresponds to table_WebBid.stBidNo = bid_no. ORM overloads the == as = in db
    # session.query(SMI) -> corresponds to a SELECT query
    # session.query(exists()) -> corresponds to SELECT EXISTS()
    # scalar() is to select the first column of the first row of the objects sent by the session.query