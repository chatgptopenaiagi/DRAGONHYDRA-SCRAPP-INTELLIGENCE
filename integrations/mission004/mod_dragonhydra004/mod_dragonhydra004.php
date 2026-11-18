<?php
defined('_JEXEC') or die;
require_once __DIR__ . '/bridge.php';
$escape = static fn($v) => htmlspecialchars((string)$v, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
try {
    $status = dh004_read((int)$params->get('port', 18976), (string)$params->get('key_path'), 'status');
    $records = dh004_read((int)$params->get('port', 18976), (string)$params->get('key_path'), 'observations');
    echo '<section><h2>DRAGONHYDRA Intelligence</h2><p>' . $escape($status['mode']) . ' · ' . $escape($status['summary']['observations']) . ' retained observations</p><p>Read-only historical evidence. No live-bookmaker claim.</p><table><thead><tr><th>Source</th><th>Value</th><th>Provenance</th></tr></thead><tbody>';
    foreach ($records['rows'] as $row) { echo '<tr><td>'.$escape($row['source_id'].' / '.$row['key']).'</td><td>'.$escape($row['value'] ?? $row['text'] ?? '').'</td><td>'.$escape($row['origin']).'</td></tr>'; }
    echo '</tbody></table></section>';
} catch (Throwable $e) { echo '<section role="status"><h2>DRAGONHYDRA unavailable</h2><p>Start the configured candidate and verify the dedicated bridge credential. No records have been substituted.</p></section>'; }
