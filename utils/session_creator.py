from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

def create_database_session(database_url: str) -> Session:
    """
    Create a database session given the database URL.

    Args:
        database_url (str): The URL of the database.
    
    Returns:
        Session: The database session.
    """
    engine = create_engine(database_url, echo=False)

    Session = sessionmaker(bind=engine)

    session = Session()

    return session ,engine