from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models import UserRecommendation, UserRequest
from app.items import ITEMS_MAPPING
from app.field_mapping import PROFILE_FIELD_NAMES
from app.database import SessionLocal
from pydantic import BaseModel
import pika
import json
import os
from app.models import model_to_dict, UserRecommendation, UserRequest
from app.utils import get_product_info

router = APIRouter()

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq//")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/recommendations/{user_id}")
def read_recommendations(user_id: int, db: Session = Depends(get_db)):
    user = (
        db.query(UserRecommendation)
        .filter(UserRecommendation.household_key == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Теперь user доступен
    profile = {
        PROFILE_FIELD_NAMES[key]: value
        for key, value in model_to_dict(user).items()
        if key in PROFILE_FIELD_NAMES
    }

    recommendations_with_info = [get_product_info(pid) for pid in user.recommendations]

    return {
        "household_key": user.household_key,
        "profile": profile,
        "recommendations": recommendations_with_info,
    }


@router.get("/requests/{telegram_login}")
def get_last_requests(telegram_login: str, db: Session = Depends(get_db)):
    requests = (
        db.query(UserRequest)
        .filter(UserRequest.telegram_login == telegram_login)
        .order_by(UserRequest.timestamp.desc())
        .limit(5)
        .all()
    )

    if not requests:
        return {"detail": "Запросов не найдено"}

    return {
        "requests": [
            {
                "requested_user_id": req.requested_user_id,
                "request_type": req.request_type,
                "timestamp": req.timestamp.isoformat(),
            }
            for req in requests
        ]
    }


class EnqueueRequest(BaseModel):
    user_id: int


def send_to_queue(user_id):
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.queue_declare(queue="recommendation_requests", durable=True)
    channel.basic_publish(
        exchange="",
        routing_key="recommendation_requests",
        body=json.dumps({"user_id": user_id}),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    connection.close()


@router.post("/enqueue")
def enqueue_recommendation(request: EnqueueRequest):
    send_to_queue(request.user_id)
    return {"status": "queued", "user_id": request.user_id}


@router.get("/results/{user_id}")
def get_cached_result(user_id: int, db: Session = Depends(get_db)):
    # Можно кэшировать в Redis или в БД
    user = (
        db.query(UserRecommendation)
        .filter(UserRecommendation.household_key == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Результат не найден")

    return {"profile": {...}, "recommendations": [...]}


# Добавь новый эндпоинт сюда
@router.get("/results/{user_id}")
def get_cached_result(user_id: int, db: Session = Depends(get_db)):
    user = (
        db.query(UserRecommendation)
        .filter(UserRecommendation.household_key == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Результат не найден")

    profile = {
        PROFILE_FIELD_NAMES[key]: getattr(user, key)
        for key in PROFILE_FIELD_NAMES
        if hasattr(user, key)
    }

    return {
        "household_key": user.household_key,
        "profile": profile,
        "recommendations": [
            get_product_info(pid) for pid in user.recommendations or []
        ],
    }
