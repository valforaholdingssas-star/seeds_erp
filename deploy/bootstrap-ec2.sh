#!/usr/bin/env bash
# Bootstrap mínimo de EC2 (Ubuntu 22.04/24.04) para Seeds ERP.
# Ejecutar como root o con sudo:  sudo bash deploy/bootstrap-ec2.sh
set -euo pipefail

echo "==> Actualizando sistema"
apt-get update -y
apt-get upgrade -y

echo "==> Instalando Docker"
if ! command -v docker >/dev/null 2>&1; then
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

echo "==> Docker Compose plugin"
docker compose version

echo "==> Usuario deploy (opcional)"
if id ubuntu >/dev/null 2>&1; then
  usermod -aG docker ubuntu || true
fi

echo "==> UFW: SSH + HTTP + HTTPS"
apt-get install -y ufw
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable || true

echo "==> Listo."
echo "Siguiente:"
echo "  1. Clonar el repo en /opt/seeds-erp"
echo "  2. cp .env.production.example .env.production  y editar secretos"
echo "  3. docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build"
echo "  4. Abrir http://IP_PUBLICA y cambiar el password del admin"
echo "Ver guía completa: deploy/EC2.md"
