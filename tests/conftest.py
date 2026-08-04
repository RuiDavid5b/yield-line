"""
Shared pytest fixtures for tests that hit a real Postgres database.
"""

import pytest
from sqlalchemy.orm import Session

from stock_news.storage.db import get_engine


@pytest.fixture(scope="session")
def db_engine():
    return get_engine()


@pytest.fixture
def db_session(db_engine):
    """
    A Session bound to a connection-level transaction that is always
    rolled back at teardown.
    """
    connection = db_engine.connect()
    outer_transaction = connection.begin()

    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()
