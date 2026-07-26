# app/infrastructure/database/base.py (new — first ORM models in the codebase)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass