import os
import sys
from sqlalchemy.orm.session import Session
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)
from scripts.model.smi_model import SMI

def insert_into_db(
        session: Session,
        ecgains,
        file_hash,
        bid_no,
        title,
        due_date,
        base_url,
        file_url,
        module_name,
        file_name,
        iconverted,
        file_size,
):
    row_data = SMI(
        ECGAINS = ecgains,
        stHash = file_hash,
        stBidNo = bid_no,
        stTitle = title,
        txtDescription = title,
        stdtDueDate = due_date,
        stURL1 = base_url,
        stURL2 = file_url,
        stModuleName = module_name,
        stFileName = file_name,
        iConverted = iconverted,
        stFileSize = file_size,
    )

    session.add(row_data)
    session.commit()