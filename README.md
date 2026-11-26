# OnMarket: a shop that runs inside Telegram

![CI](https://github.com/unknown700/E-commerce/actions/workflows/ci.yml/badge.svg)

A production-style e-commerce system built as a Telegram bot. Customers browse a
catalog, fill a cart, pay by cash or card and track their orders. Admins and
couriers run the whole business from the same bot.

## Features

**Customers** (English, Uzbek, German)
- Catalog with categories, product photos and live stock
- Persistent cart, promo codes, delivery or pickup with location sharing
- Cash on delivery or online card payment (Telegram Payments)
- Order history and a message on every status change

**Admins** (English)
- Orders: status flow `new → confirmed → preparing → on the way / ready → delivered`
- Products and categories: create, edit, hide, photos
- Warehouse: stock receipts, movement history, low-stock alerts, Excel export
- Couriers: assign deliveries and follow them
- Promo codes (percent or fixed, limits, expiry), payment history
- Sales reports (SQL aggregation) and an automatic daily report

**Couriers**
- Their own deliveries, pickup and delivery confirmation, cash to collect

**Engineering**
- Layered code: `handlers → services → repositories → PostgreSQL`
- Stock changes are transactional and logged; orders keep the price they were bought at
- Payment safety: the amount and the cart are re-checked before the money is taken,
  duplicate payments are ignored, paid-but-failed orders are flagged for refund
- Spam protection, a global error handler, FSM state in Redis
- Automated tests on a separate database, GitHub Actions CI, Docker Compose

## Tech stack

Python 3.12 · aiogram 3 · PostgreSQL 16 · SQLAlchemy 2 (async) · Alembic · Redis ·
APScheduler · Docker Compose · GitHub Actions · pytest

## Quick start

```bash
git clone https://github.com/unknown700/E-commerce.git
cd E-commerce
cp .env.example .env        # fill in BOT_TOKEN, ADMIN_IDS and POSTGRES_PASSWORD
docker compose up -d --build
docker compose logs -f bot
```

Create a bot with [@BotFather](https://t.me/BotFather), put its token in `.env`,
and your own Telegram ID in `ADMIN_IDS`. Open the bot and send `/start`; send
`/admin` to open the admin panel. Demo data: `docker compose exec bot python -m scripts.seed`.

Payments: for development leave `PAYMENT_PROVIDER_TOKEN` empty and set
`PAYMENT_MOCK=true` (a simulated payment button). For real card payments use a
provider token from BotFather.

## Development

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
docker compose up -d db redis                        # database and Redis only
alembic upgrade head
python -m app.main
```

## Tests

```bash
python -m pytest -q
python -m pytest --cov=app --cov-report=term-missing
```
Tests run against a separate `shop_test` database inside rolled-back transactions.

## Configuration

See [`.env.example`](.env.example) for every setting with a short description.

## Project structure

```
app/
  bot/          handlers, keyboards, middlewares, states
  services/     business rules (cart, orders, promo, payments, reports, ...)
  repositories/ database queries
  database/     SQLAlchemy models
  locales/      en / uz / de translations
  scheduler/    daily report job
migrations/     Alembic migrations
scripts/        seed data and helper scripts
tests/          pytest suite
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md).

## Not done yet

Referral program and broadcast, abandoned-cart reminders, filters and sorting,
product reviews, product variants (size, color), translated product names,
admin and courier panels in Uzbek and German.