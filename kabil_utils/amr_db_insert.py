from sqlalchemy.orm.session import Session

from model.AMR import AMR


def insert_to_amr_database(
        session: Session,
        ecgain: str,
        number: str,
        title: str,
        due_date: str,
        hash: str,
        url1: str,
        url2: str,
        description: str = None,
        broadcast_date: str = None,
    ):
    """
    Inserts data into the AMR database using the provided session. 
    
    Args:
        session: Session - the database session to use
        ecgain: str - the agency ecgain
        number: str - the number
        title: str - the title
        due_date: str - the due date
        hash: str - the hash value
        url1: str - the first URL
        url2: str - the second URL
        description: str (optional) - the description (default: None)
        broadcast_date: str (optional) - the broadcast date (default: None)
    """
    new_data = AMR( 
        agency_ecgain=ecgain,
        number=number,
        title=title,
        description=description,
        brodcast_date=broadcast_date,
        due_date=due_date,
        hash_value=hash,
        url1=url1,
        url2=url2
    )

    session.add(new_data)

    session.commit()
