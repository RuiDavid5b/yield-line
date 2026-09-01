APP_IMAGE := stock-news-app:latest
AIRFLOW_TEST_IMAGE := stock-news-airflow-test

app-image:
	docker build -t $(APP_IMAGE) ./backend

dev-up:
	docker compose up -d

dev-down:
	docker compose down

dev-build:
	docker compose build

dev-rebuild:
	docker compose up -d --build

api-up:
	docker compose up -d api

api-down:
	docker compose stop api

api-rebuild:
	docker compose up -d --build api

sync-companies:
	uv run python -m stock_news.graph.loader

airflow-test-image:
	docker build --target test -t $(AIRFLOW_TEST_IMAGE) -f airflow/Dockerfile airflow/

airflow-test: airflow-test-image
	docker run --rm --entrypoint pytest \
	  -v $(PWD)/airflow/dags:/opt/airflow/dags \
	  -v $(PWD)/airflow/tests:/opt/airflow/tests \
	  $(AIRFLOW_TEST_IMAGE) /opt/airflow/tests/

test-env-up:
	docker compose -f docker-compose.test.yml up -d --wait
	cd backend && \
	DATABASE_URL="postgresql+psycopg://test:test@localhost:5433/stock_news_test" \
	  uv run alembic upgrade head

test-env-down:
	docker compose -f docker-compose.test.yml down

test:
	cd backend && \
	DATABASE_URL="postgresql+psycopg://test:test@localhost:5433/stock_news_test" \
	REDIS_URL="redis://localhost:6380/0" \
	uv run pytest tests/ $(ARGS)
