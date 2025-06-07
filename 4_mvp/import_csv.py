import csv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import UserRecommendation, UserRequest
from dotenv import load_dotenv
from app.database import Base
import os
from sqlalchemy.exc import OperationalError
import time

load_dotenv()

# Подключение к БД
engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

# Ждём, пока БД будет доступна
for _ in range(10):
    try:
        Base.metadata.create_all(bind=engine)
        break
    except OperationalError:
        print("⏳ Waiting for database...")
        time.sleep(1)
else:
    raise Exception("Database not available")

SessionLocal = sessionmaker(bind=engine)


def parse_row(row):
    return {
        "household_key": int(row["household_key"]),
        "age_desc": row["AGE_DESC"],
        "income_desc": row["INCOME_DESC"],
        "marital_status_code": row["MARITAL_STATUS_CODE"],
        "homeowner_desc": row["HOMEOWNER_DESC"],
        "hh_comp_desc": row["HH_COMP_DESC"],
        "household_size_desc": row["HOUSEHOLD_SIZE_DESC"],
        "kid_category_desc": row["KID_CATEGORY_DESC"],
        "recommendations": [int(row[f"rec_{i}"]) for i in range(1, 11)],
    }


def main():
    # Очистка и создание таблицы
    UserRecommendation.__table__.drop(engine, checkfirst=True)
    UserRecommendation.__table__.create(engine, checkfirst=True)
    db = SessionLocal()
    csv_path = "data/recommendations_results.csv"

    if not os.path.exists(csv_path):
        print(f"Файл {csv_path} не найден!")
        return

    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                data = parse_row(row)
                db.add(UserRecommendation(**data))
            except Exception as e:
                print(
                    f"Ошибка при обработке строки household_key={row.get('household_key')}: {e}"
                )

        db.commit()
        print("CSV успешно загружен в PostgreSQL")


if __name__ == "__main__":
    main()
