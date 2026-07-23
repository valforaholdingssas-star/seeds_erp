<?php
if (!defined('ABSPATH')) {
    exit;
}

class Seeds_ERP_Client {
    public static function build_canonical_payload(WC_Order $order, string $event, array $opts): array {
        $cedula_key = $opts['cedula_meta_key'] ?? 'billing_cedula';
        $id_number = $order->get_meta($cedula_key);
        if (!$id_number) {
            // Common fallbacks
            foreach (['billing_cedula', '_billing_cedula', 'cedula', 'CC'] as $key) {
                $id_number = $order->get_meta($key);
                if ($id_number) {
                    break;
                }
            }
        }

        $line_items = [];
        foreach ($order->get_items() as $item) {
            $product = $item->get_product();
            $meta = [];
            foreach ($item->get_meta_data() as $m) {
                $data = $m->get_data();
                $meta[] = [
                    'key'   => $data['key'] ?? '',
                    'value' => $data['value'] ?? '',
                ];
            }
            $line_items[] = [
                'id'         => $item->get_id(),
                'product_id' => $item->get_product_id(),
                'name'       => $item->get_name(),
                'quantity'   => $item->get_quantity(),
                'total'      => $item->get_total(),
                'meta_data'  => $meta,
                'sku'        => $product ? $product->get_sku() : '',
            ];
        }

        $meta_data = [];
        foreach ($order->get_meta_data() as $m) {
            $data = $m->get_data();
            $meta_data[] = [
                'key'   => $data['key'] ?? '',
                'value' => $data['value'] ?? '',
            ];
        }
        // Ensure cédula is present by key for ERP fallback
        if ($id_number) {
            $meta_data[] = ['key' => $cedula_key, 'value' => $id_number];
        }

        return [
            'event'      => $event,
            'source'     => 'seeds-erp-sync',
            'id'         => $order->get_id(),
            'status'     => $order->get_status(),
            'total'      => $order->get_total(),
            'shipping_total' => $order->get_shipping_total(),
            'payment_method' => $order->get_payment_method(),
            'payment_method_title' => $order->get_payment_method_title(),
            'date_created' => $order->get_date_created()
                ? $order->get_date_created()->date('c')
                : null,
            'customer_id' => $order->get_customer_id(),
            'customer_note' => $order->get_customer_note(),
            'id_number'  => (string) $id_number,
            'billing'    => [
                'first_name' => $order->get_billing_first_name(),
                'last_name'  => $order->get_billing_last_name(),
                'email'      => $order->get_billing_email(),
                'phone'      => $order->get_billing_phone(),
                'address_1'  => $order->get_billing_address_1(),
                'address_2'  => $order->get_billing_address_2(),
                'city'       => $order->get_billing_city(),
                'state'      => $order->get_billing_state(),
                'postcode'   => $order->get_billing_postcode(),
                'country'    => $order->get_billing_country(),
            ],
            'line_items' => $line_items,
            'meta_data'  => $meta_data,
        ];
    }

    public static function post(array $payload, string $event): array {
        $opts = Seeds_ERP_Admin::options();
        $base = rtrim($opts['erp_url'] ?? '', '/');
        $secret = $opts['webhook_secret'] ?? '';
        if (!$base) {
            return ['ok' => false, 'error' => 'ERP URL no configurada'];
        }

        $path = $event === 'updated'
            ? '/api/v1/webhooks/woocommerce/order-updated/'
            : '/api/v1/webhooks/woocommerce/order-created/';

        $body = wp_json_encode($payload);
        $signature = hash_hmac('sha256', $body, $secret);

        $response = wp_remote_post($base . $path, [
            'timeout' => 20,
            'headers' => [
                'Content-Type'      => 'application/json',
                'X-Seeds-Signature' => $signature,
                'User-Agent'        => 'Seeds-ERP-Sync/' . SEEDS_ERP_SYNC_VERSION,
            ],
            'body' => $body,
        ]);

        if (is_wp_error($response)) {
            return ['ok' => false, 'error' => $response->get_error_message()];
        }
        $code = (int) wp_remote_retrieve_response_code($response);
        if ($code >= 200 && $code < 300) {
            return ['ok' => true, 'status' => $code];
        }
        return [
            'ok'     => false,
            'error'  => 'HTTP ' . $code . ' ' . substr((string) wp_remote_retrieve_body($response), 0, 300),
            'status' => $code,
        ];
    }
}
