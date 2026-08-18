from sqlalchemy.orm.session import Session
import sys
import os
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)
from model.spiderrecord_model import SPIDERRECORD
def insert_into_record_db(
        session:Session,
        module_name:str,
        total_bid:int,
        total_new_bid:int,
        total_new_bid_files:int,
        ecgain:str,
        timeelapsed:str
):
    row = SPIDERRECORD(
        moduleName = module_name,
        totalBid = total_bid,
        totalNewBid = total_new_bid,
        totalNewBidFile = total_new_bid_files,
        ecgain = ecgain,
        timeElapsed = timeelapsed
    )

    session.add(row)

    session.commit()

    print("Records inserted successfully")

    session.close()