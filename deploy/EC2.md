# Seeds ERP — Deploy en Amazon EC2

Guía para subir el monorepo a **una sola EC2** con Docker Compose (api + worker + beat + Postgres PostGIS + Redis + nginx + SPA).

---

## 1. Qué vas a tener

```
Internet → :80/:443 (nginx)
              ├─ /        → frontend (SPA)
              ├─ /api/    → Django/Gunicorn
              └─ /admin/  → Django admin
         red interna Docker
              ├─ api, worker, beat
              ├─ db (PostGIS)   ← volumen persistente
              └─ redis
```

Webhooks Kommo/Woo apuntan a:

```text
http://52.5.54.227/api/v1/webhooks/kommo/lead-status-changed/
http://52.5.54.227/api/v1/webhooks/woocommerce/order-created/
```

(Con dominio + HTTPS, cambia a `https://TU_DOMINIO/...`.)

**Elastic IP actual:** `52.5.54.227`

---

## 2. Requisitos EC2 (recomendado)

| Item | Mínimo razonable |
|---|---|
| AMI | Ubuntu 22.04 o 24.04 LTS |
| Tipo | `t3.medium` (2 vCPU / 4 GB) o superior |
| Disco | 40 GB gp3 (Postgres + logs crecen) |
| Security Group | SSH (22) solo tu IP · HTTP 80 · HTTPS 443 |
| Elastic IP | Sí (URL estable para DNS y webhooks) |

PostGIS + Celery + Gunicorn en la misma máquina: **4 GB RAM** es el piso cómodo.

---

## 3. Preparar la instancia (una vez)

```bash
# SSH
ssh -i tu-key.pem ubuntu@TU_IP

# Bootstrap Docker + firewall
curl -fsSL https://raw.githubusercontent.com/…   # o copia el repo y:
sudo bash deploy/bootstrap-ec2.sh
```

Desde tu máquina (con el repo):

```bash
# Opción A: git clone en el server
ssh ubuntu@TU_IP
cd /opt
sudo git clone <URL_DEL_REPO> seeds-erp
sudo chown -R ubuntu:ubuntu seeds-erp
cd seeds-erp

# Opción B: rsync desde tu Mac
rsync -avz --exclude node_modules --exclude .git \
  --exclude backend/.env --exclude frontend/node_modules \
  ./ ubuntu@TU_IP:/opt/seeds-erp/
```

---

## 4. Variables de entorno

```bash
cd /opt/seeds-erp
cp .env.production.example .env.production
nano .env.production
```

**Obligatorio generar secretos nuevos** (no uses los de local):

```bash
# DJANGO_SECRET_KEY
openssl rand -hex 32

# SEEDS_SECRETS_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# POSTGRES_PASSWORD + DJANGO_SUPERUSER_PASSWORD: contraseñas fuertes
```

Rellena:

- `DJANGO_ALLOWED_HOSTS` = dominio o IP pública  
- `CSRF_TRUSTED_ORIGINS` / `CORS_ALLOWED_ORIGINS` = `https://tu-dominio` (o `http://IP` al inicio)  
- `DJANGO_SUPERUSER_EMAIL` / `PASSWORD`

> **Importante:** `SEEDS_SECRETS_KEY` cifra tokens Envia/Alegra/Kommo del panel. Si la cambias después, pierdes esos secretos cifrados (hay que volver a cargarlos).

---

## 5. Levantar producción

```bash
cd /opt/seeds-erp
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
```

Abrir: `http://TU_IP` → login con el admin del `.env.production`.

Health:

```bash
curl -s http://TU_IP/api/health/
```

---

## 6. Dominio + HTTPS (recomendado antes de Kommo/Woo)

1. DNS A → Elastic IP  
2. En el servidor, certbot en el host **o** certificados montados en `deploy/certs/`  
3. Descomentar el bloque SSL en `deploy/nginx/conf.d/default.conf`  
4. En `.env.production`:

```env
CSRF_TRUSTED_ORIGINS=https://erp.tudominio.com
CORS_ALLOWED_ORIGINS=https://erp.tudominio.com
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
SECURE_SSL_REDIRECT=true
SECURE_HSTS_SECONDS=31536000
```

5. Recargar:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

### Certbot rápido (host)

```bash
sudo apt-get install -y certbot
# Detén nginx del compose un momento o usa DNS challenge.
# Opción práctica: terminar SSL en un Application Load Balancer (ALB) de AWS
# y dejar la EC2 solo en HTTP interno — más limpio en AWS.
```

**Opción AWS limpia:** ALB + certificado ACM → target group → EC2:80.  
Entonces el compose solo escucha 80 y `X-Forwarded-Proto` ya viene `https`.

---

## 7. Post-deploy (panel ERP)

1. Cambiar password del admin.  
2. **Configuración** → tokens Envia, Alegra, Woo, Kommo → Probar conexión.  
3. Pegar URLs de webhooks en Woo/Kommo con el dominio HTTPS.  
4. Opcional: `SEEDS_BOOTSTRAP_SEEDS=0` en redeploys para no re-sembrar datos demo.

---

## 8. Operación diaria

```bash
# Logs
docker compose -f docker-compose.prod.yml logs -f api worker

# Redeploy tras git pull
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

# Backup Postgres
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U seeds seeds_erp | gzip > backup-$(date +%F).sql.gz
```

---

## 9. Checklist de seguridad

- [ ] Security Group: 22 solo tu IP; 5432/6379 **no** públicos  
- [ ] Secretos nuevos (no los de sandbox local)  
- [ ] Admin password fuerte  
- [ ] HTTPS antes de webhooks reales  
- [ ] Backups de volumen `seeds_pgdata_prod` o `pg_dump` periódico  
- [ ] Snapshots EBS semanales  

---

## 10. Coste aproximado (orientativo)

| Recurso | Orden de magnitud |
|---|---|
| t3.medium on-demand | ~USD 30–40 / mes |
| 40 GB gp3 | ~USD 3–4 / mes |
| Elastic IP (asociada) | gratis |

RDS PostGIS aparte sube costo y complejidad; para el primer go-live **Postgres en Docker en la misma EC2** es suficiente si haces backups.

---

## Comandos de un vistazo

```bash
sudo bash deploy/bootstrap-ec2.sh
cp .env.production.example .env.production   # editar
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```
