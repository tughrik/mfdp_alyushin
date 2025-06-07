from sqlalchemy import Column, Integer, String, ARRAY, DateTime, func
from app.database import Base
from sqlalchemy.orm import class_mapper
from app.field_mapping import PROFILE_FIELD_NAMES
from app.utils import get_product_info


class UserRecommendation(Base):
    __tablename__ = "user_recommendations"

    household_key = Column(Integer, primary_key=True)
    age_desc = Column(String)
    income_desc = Column(String)
    marital_status_code = Column(String)
    homeowner_desc = Column(String)
    hh_comp_desc = Column(String)
    household_size_desc = Column(String)
    kid_category_desc = Column(String)
    recommendations = Column(ARRAY(Integer))


class UserRequest(Base):
    __tablename__ = "user_requests"

    id = Column(Integer, primary_key=True)
    telegram_login = Column(String, index=True)  # Например: artemlyushin
    requested_user_id = Column(Integer)  # household_key
    timestamp = Column(DateTime, default=func.now())
    request_type = Column(String)  # 'manual' или 'random'


def model_to_dict(model):
    from sqlalchemy.orm import class_mapper

    return {c.key: getattr(model, c.key) for c in class_mapper(model.__class__).columns}
