"""
Shared pytest fixtures for tests that hit a real Postgres database.
"""

import pytest
from sqlalchemy.orm import Session

from stock_news.storage.db import get_engine


@pytest.fixture
def db_session():
    """
    A Session bound to a connection-level transaction that is always
    rolled back at teardown.
    """
    engine = get_engine()
    connection = engine.connect()
    transaction = connection.begin()

    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()
