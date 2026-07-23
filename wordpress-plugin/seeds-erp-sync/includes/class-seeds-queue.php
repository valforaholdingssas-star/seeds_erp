<?php
if (!defined('ABSPATH')) {
    exit;
}

class Seeds_ERP_Queue {
    const TABLE = 'seeds_erp_queue';

    public static function table() {
        global $wpdb;
        return $wpdb->prefix . self::TABLE;
    }

    public static function maybe_install() {
        global $wpdb;
        $table = self::table();
        $charset = $wpdb->get_charset_collate();
        $sql = "CREATE TABLE IF NOT EXISTS {$table} (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            order_id BIGINT UNSIGNED NOT NULL,
            event_type VARCHAR(32) NOT NULL DEFAULT 'created',
            payload LONGTEXT NOT NULL,
            attempts INT UNSIGNED NOT NULL DEFAULT 0,
            next_attempt_at DATETIME NULL,
            last_error TEXT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            KEY status_next (status, next_attempt_at),
            KEY order_id (order_id)
        ) {$charset};";
        require_once ABSPATH . 'wp-admin/includes/upgrade.php';
        dbDelta($sql);
    }

    public static function enqueue(array $payload, string $event, int $order_id) {
        global $wpdb;
        $now = current_time('mysql');
        $wpdb->insert(
            self::table(),
            [
                'order_id'        => $order_id,
                'event_type'      => $event,
                'payload'         => wp_json_encode($payload),
                'attempts'        => 0,
                'next_attempt_at' => $now,
                'status'          => 'pending',
                'created_at'      => $now,
                'updated_at'      => $now,
            ],
            ['%d', '%s', '%s', '%d', '%s', '%s', '%s', '%s']
        );
    }

    public static function process_batch() {
        global $wpdb;
        $table = self::table();
        $now = current_time('mysql');
        $rows = $wpdb->get_results(
            $wpdb->prepare(
                "SELECT * FROM {$table} WHERE status = 'pending' AND next_attempt_at <= %s ORDER BY id ASC LIMIT 20",
                $now
            )
        );
        foreach ($rows as $row) {
            self::deliver($row);
        }
    }

    public static function process_one_for_order(int $order_id) {
        global $wpdb;
        $table = self::table();
        $row = $wpdb->get_row(
            $wpdb->prepare(
                "SELECT * FROM {$table} WHERE order_id = %d AND status = 'pending' ORDER BY id DESC LIMIT 1",
                $order_id
            )
        );
        if ($row) {
            self::deliver($row);
        }
    }

    private static function deliver($row) {
        global $wpdb;
        $payload = json_decode($row->payload, true);
        if (!is_array($payload)) {
            $wpdb->update(self::table(), ['status' => 'failed', 'last_error' => 'payload inválido'], ['id' => $row->id]);
            return;
        }
        $result = Seeds_ERP_Client::post($payload, $row->event_type);
        $attempts = (int) $row->attempts + 1;
        $now = current_time('mysql');
        if (!empty($result['ok'])) {
            $wpdb->update(
                self::table(),
                [
                    'status'     => 'sent',
                    'attempts'   => $attempts,
                    'last_error' => '',
                    'updated_at' => $now,
                ],
                ['id' => $row->id]
            );
            return;
        }
        // Backoff: 1m, 5m, 15m, 1h, 6h
        $delays = [60, 300, 900, 3600, 21600];
        $delay = $delays[min($attempts - 1, count($delays) - 1)];
        $status = $attempts >= 12 ? 'failed' : 'pending';
        $wpdb->update(
            self::table(),
            [
                'status'          => $status,
                'attempts'        => $attempts,
                'next_attempt_at' => gmdate('Y-m-d H:i:s', time() + $delay),
                'last_error'      => substr((string) ($result['error'] ?? 'error'), 0, 1000),
                'updated_at'      => $now,
            ],
            ['id' => $row->id]
        );
    }

    public static function stats() {
        global $wpdb;
        $table = self::table();
        $pending = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$table} WHERE status = 'pending'");
        $failed  = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$table} WHERE status = 'failed'");
        $sent    = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$table} WHERE status = 'sent'");
        return compact('pending', 'failed', 'sent');
    }
}
