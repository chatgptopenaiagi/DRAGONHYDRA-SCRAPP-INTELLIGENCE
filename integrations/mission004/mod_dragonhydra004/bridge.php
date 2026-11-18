<?php
declare(strict_types=1);
function dh004_read(int $port, string $keyPath, string $operation = 'status'): array {
    if ($port < 1024 || $port > 65535 || !in_array($operation, ['status','observations'], true)) {
        throw new RuntimeException('Invalid bridge configuration');
    }
    $resolved = realpath($keyPath);
    if ($resolved === false || !is_file($resolved) || basename($resolved) !== 'bridge.key') {
        throw new RuntimeException('Dedicated read-only bridge key is unavailable');
    }
    $key = trim((string)file_get_contents($resolved));
    if (strlen($key) < 60 || preg_match('/[\r\n]/', $key)) { throw new RuntimeException('Invalid bridge credential'); }
    $curl = curl_init('http://127.0.0.1:' . $port . '/api/' . $operation . ($operation === 'observations' ? '?limit=20' : ''));
    curl_setopt_array($curl, [CURLOPT_RETURNTRANSFER=>true, CURLOPT_PROXY=>'', CURLOPT_CONNECTTIMEOUT=>3, CURLOPT_TIMEOUT=>8,
        CURLOPT_FOLLOWLOCATION=>false, CURLOPT_HTTPHEADER=>['X-DH-Bridge: '.$key,'Accept: application/json']]);
    $body = curl_exec($curl); $code = curl_getinfo($curl, CURLINFO_HTTP_CODE); curl_close($curl);
    if ($body === false || $code !== 200 || strlen($body) > 2000000) { throw new RuntimeException('Authenticated DRAGONHYDRA bridge is unavailable'); }
    return json_decode($body, true, 64, JSON_THROW_ON_ERROR);
}
