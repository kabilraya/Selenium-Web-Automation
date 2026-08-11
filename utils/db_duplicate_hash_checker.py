from sqlalchemy.sql import exists
from sqlalchemy.orm.session import Session
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.model.smi_model import SMI
def check_for_duplicate_hash(session: Session, hash: str) -> bool:
    """
    Check if a duplicate hash exists in the session.

    Args:
        session (Session): The session object used to query the database.
        hash (str): The hash to check for duplicates.

    Returns:
        bool: True if a duplicate hash exists, False otherwise.
    """
    return session.query(exists().where(SMI.stHash == hash)).scalar()