<?php
if (!defined('ABSPATH')) {
    exit;
}

class Seeds_ERP_Admin {
    const OPTION = 'seeds_erp_sync_options';

    public static function init() {
        add_action('admin_menu', [__CLASS__, 'menu']);
        add_action('admin_init', [__CLASS__, 'register']);
    }

    public static function options(): array {
        $defaults = [
            'enabled'         => 0,
            'erp_url'         => 'https://erp.seeds.co',
            'webhook_secret'  => '',
            'cedula_meta_key' => 'billing_cedula',
        ];
        $opts = get_option(self::OPTION, []);
        if (!is_array($opts)) {
            $opts = [];
        }
        return array_merge($defaults, $opts);
    }

    public static function menu() {
        add_submenu_page(
            'woocommerce',
            'Seeds ERP Sync',
            'Seeds ERP',
            'manage_woocommerce',
            'seeds-erp-sync',
            [__CLASS__, 'render']
        );
    }

    public static function register() {
        register_setting('seeds_erp_sync', self::OPTION, [
            'type'              => 'array',
            'sanitize_callback' => [__CLASS__, 'sanitize'],
        ]);
    }

    public static function sanitize($input) {
        return [
            'enabled'         => empty($input['enabled']) ? 0 : 1,
            'erp_url'         => esc_url_raw($input['erp_url'] ?? ''),
            'webhook_secret'  => sanitize_text_field($input['webhook_secret'] ?? ''),
            'cedula_meta_key' => sanitize_text_field($input['cedula_meta_key'] ?? 'billing_cedula'),
        ];
    }

    public static function render() {
        if (!current_user_can('manage_woocommerce')) {
            return;
        }
        $opts = self::options();
        $stats = Seeds_ERP_Queue::stats();
        ?>
        <div class="wrap">
            <h1>Seeds ERP Sync</h1>
            <p>Envía órdenes a Seeds ERP con firma HMAC y cola de reintentos.</p>
            <form method="post" action="options.php">
                <?php settings_fields('seeds_erp_sync'); ?>
                <table class="form-table" role="presentation">
                    <tr>
                        <th scope="row">Activo</th>
                        <td>
                            <label>
                                <input type="checkbox" name="<?php echo esc_attr(self::OPTION); ?>[enabled]" value="1" <?php checked($opts['enabled'], 1); ?> />
                                Enviar webhooks al ERP
                            </label>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">URL del ERP</th>
                        <td>
                            <input type="url" class="regular-text" name="<?php echo esc_attr(self::OPTION); ?>[erp_url]" value="<?php echo esc_attr($opts['erp_url']); ?>" placeholder="https://erp.seeds.co" />
                            <p class="description">Sin slash final. Endpoints: /api/v1/webhooks/woocommerce/…</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Secreto HMAC</th>
                        <td>
                            <input type="password" class="regular-text" name="<?php echo esc_attr(self::OPTION); ?>[webhook_secret]" value="<?php echo esc_attr($opts['webhook_secret']); ?>" autocomplete="new-password" />
                            <p class="description">Debe coincidir con <code>woocommerce.webhook_secret</code> en el ERP.</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Meta key cédula</th>
                        <td>
                            <input type="text" class="regular-text" name="<?php echo esc_attr(self::OPTION); ?>[cedula_meta_key]" value="<?php echo esc_attr($opts['cedula_meta_key']); ?>" />
                        </td>
                    </tr>
                </table>
                <?php submit_button('Guardar'); ?>
            </form>

            <h2>Cola</h2>
            <ul>
                <li>Pendientes: <strong><?php echo (int) $stats['pending']; ?></strong></li>
                <li>Enviados: <strong><?php echo (int) $stats['sent']; ?></strong></li>
                <li>Fallidos: <strong><?php echo (int) $stats['failed']; ?></strong></li>
            </ul>
            <p>Health: <code><?php echo esc_html(home_url('/wp-json/seeds-erp/v1/health')); ?></code></p>
            <p>Resync (POST, auth admin): <code><?php echo esc_html(home_url('/wp-json/seeds-erp/v1/resync')); ?></code> body JSON <code>{"after":"2026-01-01","before":"2026-12-31"}</code></p>
        </div>
        <?php
    }
}
