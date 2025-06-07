from fastapi import APIRouter
from app.database import SessionLocal
from app.models import UserRequest

router = APIRouter(prefix="/debug", tags=["Debug"])


@router.get("/check_requests")
def check_requests():
    db = SessionLocal()
    requests = db.query(UserRequest).limit(5).all()
    return {
        "count": len(requests),
        "requests": [
            {
                "login": r.telegram_login,
                "user_id": r.requested_user_id,
                "type": r.request_type,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in requests
        ],
    }
