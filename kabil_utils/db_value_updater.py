from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine


def update_value(db_url: str, query: str, new_values: dict, condition_values: dict) -> None:
    """Update values in the database based on a custom SQL query with multiple columns and conditions.

    Args:
    - db_url (str): The URL of the database.
    - query (str): Custom SQL query for the update operation.
    - new_values (dict): Dictionary of column names and new values to set.
    - condition_values (dict): Dictionary of column names and condition values to use.

    Returns:
        None
    
    Example usage:
        Update the column 'file_name' where 'id' is equal to 123 and set it to 'your file name'.\n
        update_value(
            db_url="sqlite:///mydatabase.db",
            query="UPDATE mytable SET file_name = :new_file_name WHERE id = :id",
            new_values={"new_file_name": "your file name"},
            condition_values={"id": 123}
        )
    """
    engine: Engine = create_engine(db_url, connect_args={"ssl_disabled": True})

    with engine.begin() as connection:
        # result: Connection.ResultProxy = connection.execute(
        result = connection.execute(
            text(query),
            {**new_values, **condition_values},
        )

    print(f"{result.rowcount} rows updated.")
