FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# dependencies first: this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY scripts ./scripts

# do not run the bot as root
RUN useradd --create-home --uid 1000 botuser
USER botuser

# apply the database migrations, then start the bot
CMD ["sh", "-c", "alembic upgrade head && exec python -m app.main"]