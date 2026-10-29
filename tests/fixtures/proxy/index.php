<?php
// Test-only endpoint: uses the accepted image's middleware, not its application
// bootstrap, database, queue, scheduler or credentials. Never deploy this file.
require '/var/www/html/vendor/autoload.php';

$container = new Illuminate\Container\Container();
Illuminate\Container\Container::setInstance($container);
$config = new Illuminate\Config\Repository([
    'ninja' => ['trusted_proxies' => getenv('TRUSTED_PROXIES')],
    'trustedproxy' => ['proxies' => []],
]);
$container->instance('config', $config);
$middleware = new App\Http\Middleware\TrustProxies($config);
$request = Illuminate\Http\Request::capture();
$result = $middleware->handle($request, static function ($request) {
    return [
        'ip' => $request->ip(),
        'scheme' => $request->getScheme(),
        'host' => $request->getHost(),
        'port' => $request->getPort(),
        'url' => $request->url(),
        'path' => $request->path(),
        'authorization' => $request->header('Authorization'),
        'api_token' => $request->header('X-API-Token'),
        'cookie' => $request->cookie('proxy_smoke'),
        'forwarded' => array_filter($request->headers->all(), static function ($name) {
            return $name === 'forwarded' || str_starts_with($name, 'x-forwarded-');
        }, ARRAY_FILTER_USE_KEY),
    ];
});
header('Content-Type: application/json');
echo json_encode($result, JSON_THROW_ON_ERROR);
