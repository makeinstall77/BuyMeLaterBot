# BuyMeLaterBot — LXC на Proxmox

## Сеть

| Хост | IP | Роль |
|------|-----|------|
| `pg.sweethome.local` | 172.16.10.150 | PostgreSQL (общий) |
| `buymelater.lan` | **172.16.10.160** | Bot + API |

## PostgreSQL

На `pg.sweethome.local` создать БД (если ещё нет):

```bash
sudo -u postgres psql <<'SQL'
CREATE USER buymelater WITH PASSWORD 'YOUR_PASSWORD';
CREATE DATABASE buymelater OWNER buymelater;
REVOKE ALL ON DATABASE buymelater FROM PUBLIC;
GRANT ALL PRIVILEGES ON DATABASE buymelater TO buymelater;
SQL
```

`pg_hba.conf`: доступ из `172.16.10.0/24`, метод `scram-sha-256`.

## LXC бота

```bash
ssh pve.sweethome.local

pct create 120 local:vztmpl/debian-12-standard_*.tar.zst \
  --hostname buymelater \
  --memory 512 --cores 1 --rootfs local-lvm:8 \
  --net0 name=eth0,bridge=vmbr0,ip=172.16.10.160/24,gw=172.16.10.1 \
  --features nesting=1

pct start 120
```

## Деплой

```bash
pct enter 120
apt update && apt install -y docker.io docker-compose-plugin git
git clone git@github.com:makeinstall77/BuyMeLaterBot.git /opt/buymelater
cd /opt/buymelater/deploy
cp .env.example .env
# TELEGRAM_BOT_TOKEN, API_TOKEN, DATABASE_URL

docker compose up -d --build
docker compose exec app alembic upgrade head
```

## Проверка

```bash
curl http://172.16.10.160:8080/health
curl -H "Authorization: Bearer $API_TOKEN" http://172.16.10.160:8080/api/v1/scopes
```

Из HAOS:

```bash
ssh root@haos
curl http://172.16.10.160:8080/health
```
