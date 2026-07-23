<?php
/**
 * Plugin Name: Seeds ERP Sync
 * Description: Envía órdenes WooCommerce al ERP Seeds con firma HMAC, payload canónico y cola de reintentos.
 * Version: 1.0.0
 * Author: Seeds
 * Requires at least: 6.0
 * Requires PHP: 7.4
 * WC requires at least: 7.0
 * Text Domain: seeds-erp-sync
 */

if (!defined('ABSPATH')) {
    exit;
}

define('SEEDS_ERP_SYNC_VERSION', '1.0.0');
define('SEEDS_ERP_SYNC_PATH', plugin_dir_path(__FILE__));
define('SEEDS_ERP_SYNC_URL', plugin_dir_url(__FILE__));

require_once SEEDS_ERP_SYNC_PATH . 'includes/class-seeds-queue.php';
require_once SEEDS_ERP_SYNC_PATH . 'includes/class-seeds-client.php';
require_once SEEDS_ERP_SYNC_PATH . 'includes/class-seeds-admin.php';

final class Seeds_ERP_Sync {
    public static function init() {
        add_action('plugins_loaded', [__CLASS__, 'boot']);
    }

    public static function boot() {
        if (!class_exists('WooCommerce')) {
            add_action('admin_notices', function () {
                echo '<div class="notice notice-error"><p>Seeds ERP Sync requiere WooCommerce activo.</p></div>';
            });
            return;
        }

        Seeds_ERP_Admin::init();
        Seeds_ERP_Queue::maybe_install();

        add_action('woocommerce_new_order', [__CLASS__, 'on_new_order'], 20, 1);
        add_action('woocommerce_order_status_changed', [__CLASS__, 'on_status_changed'], 20, 4);
        add_action('seeds_erp_process_queue', [Seeds_ERP_Queue::class, 'process_batch']);

        if (!wp_next_scheduled('seeds_erp_process_queue')) {
            wp_schedule_event(time() + 60, 'minutes_5', 'seeds_erp_process_queue');
        }

        add_filter('cron_schedules', function ($schedules) {
            $schedules['minutes_5'] = [
                'interval' => 300,
                'display'  => 'Every 5 Minutes',
            ];
            return $schedules;
        });

        add_action('rest_api_init', [__CLASS__, 'register_rest']);
    }

    public static function register_rest() {
        register_rest_route('seeds-erp/v1', '/health', [
            'methods'             => 'GET',
            'permission_callback' => '__return_true',
            'callback'            => function () {
                $opts = Seeds_ERP_Admin::options();
                return [
                    'ok'      => true,
                    'enabled' => !empty($opts['enabled']),
                    'erp_url' => $opts['erp_url'] ?? '',
                    'queue'   => Seeds_ERP_Queue::stats(),
                    'version' => SEEDS_ERP_SYNC_VERSION,
                ];
            },
        ]);

        register_rest_route('seeds-erp/v1', '/resync', [
            'methods'             => 'POST',
            'permission_callback' => function () {
                return current_user_can('manage_woocommerce');
            },
            'callback'            => [__CLASS__, 'rest_resync'],
            'args'                => [
                'after'  => ['required' => true, 'type' => 'string'],
                'before' => ['required' => true, 'type' => 'string'],
            ],
        ]);
    }

    public static function rest_resync(WP_REST_Request $request) {
        $after  = sanitize_text_field($request->get_param('after'));
        $before = sanitize_text_field($request->get_param('before'));
        $orders = wc_get_orders([
            'limit'        => 100,
            'date_created' => $after . '...' . $before,
            'orderby'      => 'date',
            'order'        => 'ASC',
            'return'       => 'ids',
        ]);
        $queued = 0;
        foreach ($orders as $order_id) {
            self::enqueue_order((int) $order_id, 'updated');
            $queued++;
        }
        return ['queued' => $queued];
    }

    public static function on_new_order($order_id) {
        self::enqueue_order((int) $order_id, 'created');
    }

    public static function on_status_changed($order_id, $from, $to, $order) {
        self::enqueue_order((int) $order_id, 'updated');
    }

    public static function enqueue_order(int $order_id, string $event) {
        $opts = Seeds_ERP_Admin::options();
        if (empty($opts['enabled'])) {
            return;
        }
        $order = wc_get_order($order_id);
        if (!$order) {
            return;
        }
        $payload = Seeds_ERP_Client::build_canonical_payload($order, $event, $opts);
        Seeds_ERP_Queue::enqueue($payload, $event, $order_id);
        // Attempt immediate delivery
        Seeds_ERP_Queue::process_one_for_order($order_id);
    }

    public static function activate() {
        Seeds_ERP_Queue::maybe_install();
        if (!wp_next_scheduled('seeds_erp_process_queue')) {
            wp_schedule_event(time() + 60, 'minutes_5', 'seeds_erp_process_queue');
        }
    }

    public static function deactivate() {
        wp_clear_scheduled_hook('seeds_erp_process_queue');
    }
}

register_activation_hook(__FILE__, ['Seeds_ERP_Sync', 'activate']);
register_deactivation_hook(__FILE__, ['Seeds_ERP_Sync', 'deactivate']);
Seeds_ERP_Sync::init();
