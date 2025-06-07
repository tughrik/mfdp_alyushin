import pika
import json
from app.models import UserRecommendation
from app.database import SessionLocal
from app.items import ITEMS_MAPPING
from app.field_mapping import PROFILE_FIELD_NAMES
import time


def wait_for_rabbitmq(url, retries=10, delay=5):
    for i in range(retries):
        try:
            connection = pika.BlockingConnection(pika.URLParameters(url))
            connection.close()
            print("RabbitMQ доступен")
            return True
        except Exception as e:
            print(f"Ожидание RabbitMQ... Попытка {i + 1}/{retries}")
            time.sleep(delay)
    raise Exception("RabbitMQ не отвечает")


def get_product_info(product_id):
    info = ITEMS_MAPPING.get(product_id, {"category": "Unknown", "emoji": "❓"})
    return f"{info['emoji']} {product_id} ({info['category']})"


def process_user_recommendation(ch, method, properties, body):
    try:
        data = json.loads(body)
        user_id = data["user_id"]

        db = SessionLocal()
        user = (
            db.query(UserRecommendation)
            .filter(UserRecommendation.household_key == user_id)
            .first()
        )

        if not user:
            print(f"Пользователь {user_id} не найден")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        profile = {
            PROFILE_FIELD_NAMES[key]: value
            for key, value in vars(user).items()
            if key in PROFILE_FIELD_NAMES
        }

        recommendations_with_info = [
            get_product_info(pid) for pid in user.recommendations
        ]

        # Redis?
        print(f"Рекомендации для пользователя {user_id} обработаны.")
        print("Профиль:", profile)
        print("Рекомендации:", recommendations_with_info)

        ch.basic_publish(
            exchange="results",
            routing_key="recommendations",
            body=json.dumps(
                {
                    "user_id": user_id,
                    "profile": profile,
                    "recommendations": recommendations_with_info,
                }
            ),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print("Ошибка при обработке:", e)
        ch.basic_nack(delivery_tag=method.delivery_tag)


def start_model_workers():
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq//")
    wait_for_rabbitmq(rabbitmq_url)
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    channel = connection.channel()

    channel.queue_declare(queue="recommendation_requests", durable=True)
    channel.exchange_declare(exchange="results", exchange_type="fanout")

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue="recommendation_requests", on_message_callback=process_user_recommendation
    )

    print("Ожидание сообщений...")
    channel.start_consuming()


if __name__ == "__main__":
    from dotenv import load_dotenv
    import os

    load_dotenv()
    start_model_workers()
