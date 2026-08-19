"""
Prints all tracked companies as a JSON array to stdout. Entrypoint for
Airflow's DockerOperator to retrieve the company list via container
output/xcom, without Airflow needing stock_news importable.
"""

from __future__ import annotations

import json

from stock_news.storage.db import get_session_factory
from stock_news.storage.loaders import get_all_companies

if __name__ == "__main__":
    session_factory = get_session_factory()
    with session_factory() as session:
        companies = get_all_companies(session)
    print(json.dumps(companies))
