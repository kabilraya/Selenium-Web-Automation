from sqlalchemy.sql import exists
from sqlalchemy.orm.session import Session

from model.AMR import AMR

def check_for_duplicate_amr_hash(session: Session, hash: str) -> bool:
    """
    Check if a duplicate hash exists in the session.

    Args:
        session (Session): The session object used to query the database.
        hash (str): The hash to check for duplicates.

    Returns:
        bool: True if a duplicate hash exists, False otherwise.
    """
    return session.query(exists().where(AMR.hash_value == hash)).scalar()