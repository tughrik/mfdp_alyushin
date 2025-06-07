import logging
import random
from datetime import datetime

import pika
import json
from httpx import AsyncClient
import time

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from app.database import SessionLocal
from app.models import UserRequest
import os
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = "http://mfdp-service:8000/api/v1/recommendations"
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq//")


# Клавиатура с кнопками
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔎 Ввести ID", callback_data="enter_id")],
        [
            InlineKeyboardButton(
                "🎲 Случайный пользователь", callback_data="random_user"
            )
        ],
        [InlineKeyboardButton("📜 Мои запросы", callback_data="my_requests")],
    ]
    return InlineKeyboardMarkup(keyboard)


# Функция для сохранения истории запросов
def save_request(telegram_login: str, requested_user_id: int, request_type: str):
    db = SessionLocal()
    try:
        db.add(
            UserRequest(
                telegram_login=telegram_login,
                requested_user_id=requested_user_id,
                request_type=request_type,
            )
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка записи в БД: {e}")
    finally:
        db.close()


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "MFDP Люшин А.Ю.\nЭто рекомендательный сервис продуктов для текущих пользователей онлайн-магазина Копейка.\nВыбери действие:",
        reply_markup=get_main_keyboard(),
    )


# Обработчик нажатий на кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    telegram_login = update.effective_user.username

    if query.data == "enter_id":
        await query.edit_message_text(text="Введите ID пользователя (1-2500):")
    elif query.data == "random_user":
        user_id = random.randint(1, 2500)
        await fetch_and_send_recommendations(query, user_id, telegram_login)
    elif query.data == "my_requests":
        await show_my_requests(query, telegram_login)


# Показать последние 5 запросов
API_BASE_URL_HIST = "http://mfdp-service:8000/api/v1"


async def show_my_requests(query, telegram_login):
    try:
        response = requests.get(f"{API_BASE_URL_HIST}/requests/{telegram_login}")
        data = response.json()

        if isinstance(data, dict):
            if "detail" in data and data["detail"] == "Запросов не найдено":
                text = "Вы еще ничего не запрашивали."
            elif "requests" in data and isinstance(data["requests"], list):
                text = "📘 Последние 5 ваших запросов:\n\n"
                for req in data["requests"]:
                    req_type = (
                        "🎲 Случайный"
                        if req["request_type"] == "random"
                        else "🔎 Вручную"
                    )
                    timestamp = req["timestamp"].replace("T", " ").split(".")[0]
                    text += f"{req_type}: {req['requested_user_id']} — {timestamp}\n"
            else:
                text = "Ошибка: данные не содержат списка запросов."
        else:
            text = "Ошибка: неожидаемый формат ответа."

        if query.message.text != text:
            await query.edit_message_text(text=text, reply_markup=get_main_keyboard())

    except Exception as e:
        logging.error(e)
        await query.edit_message_text(
            "Ошибка при получении истории.", reply_markup=get_main_keyboard()
        )


# Получение рекомендаций по ID
async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    telegram_login = update.effective_user.username

    if user_input.isdigit():
        user_id = int(user_input)
        await get_recommendations(update, context, user_id, telegram_login)
    else:
        await update.message.reply_text(
            "Неверный формат. Введите число или используйте меню.",
            reply_markup=get_main_keyboard(),
        )


# Запрос к API за рекомендациями
async def get_recommendations(update, context, user_id, telegram_login):
    try:
        response = requests.get(f"{API_URL}/{user_id}")
        if response.status_code == 404:
            await update.message.reply_text(
                "Пользователь не найден.", reply_markup=get_main_keyboard()
            )
            return

        data = response.json()
        profile = data["profile"]
        recs = data["recommendations"]

        profile_str = "\n".join([f"{k}: {v}" for k, v in profile.items()])
        recommendations_str = "\n".join(recs)

        await update.message.reply_text(
            f"👤 *Профиль пользователя {user_id}*: \n{profile_str}\n\n"
            f"🛍️ Рекомендации: \n{recommendations_str}",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown",
        )

        # ✅ Теперь telegram_login доступен
        save_request(telegram_login, user_id, "manual")

    except Exception as e:
        logging.error(e)
        await update.message.reply_text(
            "Ошибка при получении данных.", reply_markup=get_main_keyboard()
        )

    except Exception as e:
        logging.error(e)
        await update.message.reply_text(
            "Ошибка при получении данных.", reply_markup=get_main_keyboard()
        )


# Универсальная функция получения рекомендаций
async def poll_for_result(user_id: int, timeout=30, interval=3):
    async with AsyncClient() as client:
        for _ in range(timeout // interval):
            response = await client.get(f"{API_BASE_URL_HIST}/results/{user_id}")
            if response.status_code == 200:
                return response.json()
            time.sleep(interval)
        return None


async def fetch_and_send_recommendations(query, user_id, telegram_login):
    try:
        response = requests.get(f"{API_URL}/{user_id}")
        if response.status_code == 404:
            await query.edit_message_text(
                text="Пользователь не найден.", reply_markup=get_main_keyboard()
            )
            return

        data = response.json()

        profile = data["profile"]
        recs = data["recommendations"]

        if not isinstance(profile, dict) or not isinstance(recs, list):
            raise ValueError("Некорректный формат данных")

        profile_str = "\n".join([f"{k}: {v}" for k, v in profile.items()])
        recommendations_str = "\n".join(recs)

        await query.edit_message_text(
            f"👤 *Профиль пользователя {user_id}*: \n{profile_str}\n\n"
            f"🛍️ Рекомендации: \n{recommendations_str}",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown",
        )

        save_request(telegram_login, user_id, "random")

    except Exception as e:
        logging.error(f"Ошибка при обработке: {e}", exc_info=True)
        await query.answer("Ошибка при получении данных.")


def send_to_model_queue(user_id):
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.queue_declare(queue="recommendation_requests", durable=True)
    channel.basic_publish(
        exchange="",
        routing_key="recommendation_requests",
        body=json.dumps({"user_id": user_id}),
        properties=pika.BasicProperties(delivery_mode=2),  # persistent message
    )
    connection.close()


# Точка входа
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(show_my_requests, pattern="^my_requests$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))

    app.run_polling()


if __name__ == "__main__":
    main()
