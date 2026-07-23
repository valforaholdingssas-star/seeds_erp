# Seeds ERP Sync (WordPress / WooCommerce)

Plugin ligero que reemplaza el webhook nativo de WooCommerce para Seeds ERP.

## Instalación

1. Copia la carpeta `seeds-erp-sync` a `wp-content/plugins/`.
2. Activa el plugin en WordPress.
3. WooCommerce → **Seeds ERP**: configura URL del ERP, secreto HMAC y meta key de cédula.
4. En el ERP (Configuración), pon el mismo valor en `woocommerce.webhook_secret`.

## Qué hace

- Hooks `woocommerce_new_order` y `woocommerce_order_status_changed`.
- Payload canónico con `id_number` explícito (no depende de índice en `meta_data`).
- Header `X-Seeds-Signature: HMAC-SHA256(body, secret)`.
- Cola persistente con backoff si el ERP no responde 2xx.
- REST: `GET /wp-json/seeds-erp/v1/health`, `POST /wp-json/seeds-erp/v1/resync`.

## Endpoints ERP

- `POST /api/v1/webhooks/woocommerce/order-created/`
- `POST /api/v1/webhooks/woocommerce/order-updated/`
