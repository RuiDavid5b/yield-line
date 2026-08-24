APP_IMAGE := stock-news-app:latest

build:
	docker build -t $(APP_IMAGE) .

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
