#!/bin/bash
# Native install on LXC (without Docker)
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/git/BuyMeLaterBot}"
cd "$APP_DIR"

sudo apt-get update
sudo apt-get install -y python3-venv python3-pip

python3 -m venv .venv
.venv/bin/pip install -U pip setuptools
.venv/bin/pip install -e .

.venv/bin/alembic upgrade head

sudo cp deploy/buymelater.service /etc/systemd/system/buymelater.service
sudo systemctl daemon-reload
sudo systemctl enable --now buymelater.service

echo "Done. Check: curl http://localhost:8080/health"
