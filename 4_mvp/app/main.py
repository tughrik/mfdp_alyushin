from fastapi import FastAPI
from app.api import router as api_router
from app.requests_api import router as requests_router
from app.database import Base, engine
from app.items import load_items_mapping
from dotenv import load_dotenv
import os
import time
from sqlalchemy.exc import OperationalError
from app.debug_api import router as debug_router

# Загрузка переменных окружения
load_dotenv()

# Загрузка справочника товаров
try:
    load_items_mapping()
except Exception as e:
    print(f"Предупреждение: Не удалось загрузить ITEMS_MAPPING — {e}")

# Ждём, пока БД будет доступна и создаём таблицы
for _ in range(10):
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("Все таблицы созданы или уже существуют")
        break
    except OperationalError:
        print("Ожидаем базу...")
        time.sleep(1)

# Создание приложения
app = FastAPI(title="MFDP Recommendation Service")
app.include_router(api_router, prefix="/api/v1")
app.include_router(requests_router, prefix="/api/v1")
app.include_router(debug_router)
