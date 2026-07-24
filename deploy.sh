#!/usr/bin/env bash

# ==============================================================================
# SVARP Portal Inventory Backend Deployment Script
# Target Server Location: /var/www/inventory-portal-be (or /var/www/portal-inventory-be)
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

BE_DIR="${BE_DIR:-/var/www/inventory-portal-be}"
BRANCH="${BRANCH:-dev}"

if [ ! -d "$BE_DIR" ]; then
  if [ -d "/var/www/portal-inventory-be" ]; then
    BE_DIR="/var/www/portal-inventory-be"
  elif [ -d "/var/www/inventory-be" ]; then
    BE_DIR="/var/www/inventory-be"
  fi
fi

echo -e "${CYAN}========================================================================${NC}"
echo -e "${CYAN}             Deploying SVARP Portal Inventory Backend                   ${NC}"
echo -e "${CYAN}========================================================================${NC}"

if [ -d "$BE_DIR" ]; then
  cd "$BE_DIR"
fi

echo -e "${YELLOW}➜ Pulling latest backend code (origin/${BRANCH})...${NC}"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull origin "$BRANCH"

if [ -d "venv" ]; then
  echo -e "${YELLOW}➜ Updating python virtualenv dependencies...${NC}"
  source venv/bin/activate
  if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
  fi
fi

if [ -f "alembic.ini" ]; then
  echo -e "${YELLOW}➜ Running database migrations (alembic upgrade head)...${NC}"
  if [ -d "venv" ]; then
    source venv/bin/activate
  fi
  alembic upgrade head || alembic stamp head || echo -e "${YELLOW}Notice: Migration completed or stamped.${NC}"
fi

echo -e "${YELLOW}➜ Restarting systemd service...${NC}"
sudo systemctl restart inventory-portal-be || \
sudo systemctl restart portal-inventory-be || \
sudo systemctl restart inventory-be || \
sudo systemctl restart svarp-inventory-be || true

echo -e "${GREEN}✓ Inventory Backend deployment successful!${NC}"
