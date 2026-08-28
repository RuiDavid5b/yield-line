"""
Engine/session setup.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from stock_news.config import get_settings


def get_engine(database_url: str | None = None):
    return create_engine(database_url or str(get_settings().database_url))


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    engine = get_engine(database_url)
    return sessionmaker(bind=engine)
