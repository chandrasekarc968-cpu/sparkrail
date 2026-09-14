import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from src.auth.models import UserTable, Role, Department
from src.auth.security import hash_password

logger = logging.getLogger("SparkRailAuth")

DEFAULT_PASSWORD = "RailOps@2026!"

SEED_PERSONNEL: List[Dict[str, Any]] = [
    {
        "pf_number": "PF-ECR-90801",
        "email": "srdom.ddu@indianrailways.gov.in",
        "full_name": "R. K. Sharma, IRTS",
        "department": Department.OPERATING,
        "role": Role.SR_DOM,
        "division_code": "ECR-DDU",
        "zone_code": "ECR",
        "is_active": True
    },
    {
        "pf_number": "PF-ECR-90802",
        "email": "ctpc.ddu@indianrailways.gov.in",
        "full_name": "A. K. Verma, IRSEE",
        "department": Department.TRD,
        "role": Role.CTPC,
        "division_code": "ECR-DDU",
        "zone_code": "ECR",
        "is_active": True
    },
    {
        "pf_number": "PF-ECR-90803",
        "email": "sse.pway.ddu@indianrailways.gov.in",
        "full_name": "Vikas Singh, SSE/P-Way",
        "department": Department.CIVIL,
        "role": Role.SSE_PWAY,
        "division_code": "ECR-DDU",
        "zone_code": "ECR",
        "is_active": True
    },
    {
        "pf_number": "PF-ECR-90804",
        "email": "sse.sig.ddu@indianrailways.gov.in",
        "full_name": "P. K. Mishra, SSE/Signal",
        "department": Department.SNT,
        "role": Role.SSE_SIGNAL,
        "division_code": "ECR-DDU",
        "zone_code": "ECR",
        "is_active": True
    },
    {
        "pf_number": "PF-ECR-90805",
        "email": "sm.ddu@indianrailways.gov.in",
        "full_name": "R. N. Yadav, Station Superintendent",
        "department": Department.OPERATING,
        "role": Role.STATION_MASTER,
        "division_code": "ECR-DDU",
        "zone_code": "ECR",
        "is_active": True
    },
    {
        "pf_number": "PF-CRIS-00001",
        "email": "admin.cris@indianrailways.gov.in",
        "full_name": "CRIS System Administrator",
        "department": Department.ADMIN,
        "role": Role.SYSTEM_ADMIN,
        "division_code": "ALL",
        "zone_code": "IR",
        "is_active": True
<<<<<<< HEAD
    },
    {
        "pf_number": "PF-ECR-90806",
        "email": "reader.ddu@indianrailways.gov.in",
        "full_name": "S. K. Gupta, Control Room Observer",
        "department": Department.OPERATING,
        "role": Role.READ_ONLY_OPERATOR,
        "division_code": "ECR-DDU",
        "zone_code": "ECR",
        "is_active": True
=======
>>>>>>> eb1ff7de39b31eff8ea9c754fe33b6232af61be3
    }
]


def seed_default_users(db: Session, password: str = DEFAULT_PASSWORD) -> List[UserTable]:
    """
    Idempotent seeder: populates realistic mock railway personnel for Pandit Deen Dayal Upadhyaya (DDU) division.
    """
    hashed = hash_password(password)
    created_or_updated: List[UserTable] = []

    for item in SEED_PERSONNEL:
        existing = db.query(UserTable).filter(
            (UserTable.pf_number == item["pf_number"]) | (UserTable.email == item["email"])
        ).first()

        if existing:
            existing.full_name = item["full_name"]
            existing.department = item["department"]
            existing.role = item["role"]
            existing.division_code = item["division_code"]
            existing.zone_code = item["zone_code"]
            existing.is_active = item["is_active"]
            existing.hashed_password = hashed
            created_or_updated.append(existing)
        else:
            new_user = UserTable(
                pf_number=item["pf_number"],
                email=item["email"],
                full_name=item["full_name"],
                hashed_password=hashed,
                department=item["department"],
                role=item["role"],
                division_code=item["division_code"],
                zone_code=item["zone_code"],
                is_active=item["is_active"]
            )
            db.add(new_user)
            created_or_updated.append(new_user)

    db.commit()
    logger.info(f"Successfully seeded {len(created_or_updated)} Indian Railways mock personnel.")
    return created_or_updated
