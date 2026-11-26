# Deployment

The bot uses long polling, so it needs **no domain, no SSL and no open ports**
except SSH. Any small Linux server (1-2 GB RAM) is enough.

## 1. Prepare a fresh Ubuntu server

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
ufw allow OpenSSH && ufw --force enable
```

## 2. Get the code and configure it

```bash
git clone https://github.com/unknown700/E-commerce.git shop-bot
cd shop-bot
cp .env.example .env
nano .env
```

Set at least:
- `BOT_TOKEN`, `ADMIN_IDS`
- a **strong** `POSTGRES_PASSWORD` (set it before the first start; changing it
  later does not change the existing database)
- `ENVIRONMENT=production` (the admins get "🟢 Bot started" on every start)
- `PAYMENT_MOCK=false` and `PAYMENT_PROVIDER_TOKEN` (the live token, only here)

Never commit `.env`. Use a **separate bot** for development and production, or
stop the development bot, because two instances with one token conflict.

## 3. Start

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f bot
```

Database migrations run automatically when the bot container starts.
The containers restart by themselves after a crash or a server reboot.

## 4. Update to a new version

```bash
cd shop-bot
git pull
docker compose up -d --build
```

## 5. Backups (important)

Daily database dump at 03:00, keeping 14 days. Open `crontab -e` and add one line
(change `shop` / `shop_db` if you changed them in `.env`):

```bash
0 3 * * * cd ~/shop-bot && docker compose exec -T db pg_dump -U shop shop_db | gzip > ~/backups/shop_$(date +\%F).sql.gz && find ~/backups -name 'shop_*.sql.gz' -mtime +14 -delete
```
Create the folder first: `mkdir -p ~/backups`. Also copy the dumps to another
machine from time to time: a backup on the same server does not survive a lost server.

Restore into an empty database:

```bash
gunzip -c ~/backups/shop_2026-11-24.sql.gz | docker compose exec -T db psql -U shop -d shop_db
```

## 6. Useful commands

```bash
docker compose logs -f bot        # live logs
docker compose restart bot        # restart the bot
docker compose stop bot           # stop the bot, keep the database
docker compose down               # stop everything, keep the data
```
**Never run `docker compose down -v`**: it deletes the database volume.

## Security checklist

- SSH keys instead of passwords, firewall on (`ufw`)
- PostgreSQL and Redis listen on `127.0.0.1` only (see `docker-compose.yml`)
- `.env` stays on the server; if a token leaks, revoke it in @BotFather
- Test payment token for development, live token only on the server