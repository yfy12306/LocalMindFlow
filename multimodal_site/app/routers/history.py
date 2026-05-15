from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat_record import ChatRecord

router = APIRouter(prefix="/history", tags=["history"])

@router.get("/")
def get_history(db: Session = Depends(get_db)):
    latest_messages = (
        db.query(ChatRecord)
        .order_by(ChatRecord.created_at.desc(), ChatRecord.id.desc())
        .limit(10)
        .all()
    )

    session_count = db.query(ChatRecord.session_id).distinct().count()

    return {
        "session_count": session_count,
        "latest_messages": [
            {
                "session_id": record.session_id,
                "role": record.role,
                "model": record.model,
                "preview": record.content[:120],
                "created_at": record.created_at,
            }
            for record in latest_messages
        ],
    }