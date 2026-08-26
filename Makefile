APP_IMAGE := stock-news-app:latest
API_IMAGE := stock-news-api:latest
AIRFLOW_TEST_IMAGE := stock-news-airflow-test

app-image:
	docker build -t $(APP_IMAGE) .

dev-up:
	docker compose up -d

dev-down:
	docker compose down

dev-build:
	docker compose build

dev-rebuild:
	docker compose up -d --build

api-image:
	docker build -t $(API_IMAGE) -f api/Dockerfile .

api-up: api-image
	docker run -d \
	  --name stock-news-api \
	  --network stock_news_net \
	  -p 8000:8000 \
	  --env-file .env \
	  $(API_IMAGE)

api-down:
	docker stop stock-news-api
	docker rm stock-news-api

airflow-test-image:
	docker build --target test -t $(AIRFLOW_TEST_IMAGE) -f airflow/Dockerfile airflow/

airflow-test: airflow-test-image
	docker run --rm --entrypoint pytest \
	  -v $(PWD)/airflow/dags:/opt/airflow/dags \
	  -v $(PWD)/airflow/tests:/opt/airflow/tests \
	  $(AIRFLOW_TEST_IMAGE) /opt/airflow/tests/

test-env-up:
	docker compose -f docker-compose.test.yml up -d --wait
	DATABASE_URL="postgresql+psycopg://test:test@localhost:5433/stock_news_test" \
	  uv run alembic upgrade head

test-env-down:
	docker compose -f docker-compose.test.yml down

test:
	DATABASE_URL="postgresql+psycopg://test:test@localhost:5433/stock_news_test" \
	REDIS_URL="redis://localhost:6380/0" \
	uv run pytest tests/ $(ARGS)
