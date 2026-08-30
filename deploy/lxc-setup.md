# BuyMeLaterBot — деплой в LXC (Proxmox)

## Обзор

- **PostgreSQL** — отдельный хост в LAN (общий для нескольких сервисов)
- **Bot LXC** — Docker Compose с приложением (бот + API)

## PostgreSQL

На хосте БД создать пользователя и базу:

```bash
sudo -u postgres psql <<'SQL'
CREATE USER buymelater WITH PASSWORD 'YOUR_PASSWORD';
CREATE DATABASE buymelater OWNER buymelater;
REVOKE ALL ON DATABASE buymelater FROM PUBLIC;
GRANT ALL PRIVILEGES ON DATABASE buymelater TO buymelater;
SQL
```

`pg_hba.conf`: разрешить доступ из вашей LAN-подсети, метод `scram-sha-256`.

## LXC бота

```bash
pct create 120 local:vztmpl/debian-12-standard_*.tar.zst \
  --hostname buymelater \
  --memory 512 --cores 1 --rootfs local-lvm:8 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --features nesting=1

pct start 120
```

## Деплой

```bash
apt update && apt install -y docker.io docker-compose-plugin git
git clone <your-repo-url> /opt/buymelater
cd /opt/buymelater/deploy
cp .env.example .env
# TELEGRAM_BOT_TOKEN, API_TOKEN, DATABASE_URL

docker compose up -d --build
docker compose exec app alembic upgrade head
```

## Проверка

```bash
curl http://<bot-host>:8080/health
curl -H "Authorization: Bearer $API_TOKEN" http://<bot-host>:8080/api/v1/scopes
```
