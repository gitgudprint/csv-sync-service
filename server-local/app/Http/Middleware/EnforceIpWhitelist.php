<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class EnforceIpWhitelist
{
    public function handle(Request $request, Closure $next): mixed
    {
        $allowedIps = config('csv_sync.allowed_ips', []);

        if (empty($allowedIps)) {
            return new JsonResponse([
                'status' => 'error',
                'message' => 'No allowed IPs configured.',
            ], 403);
        }

        $clientIp = $this->clientIp($request);

        if (!in_array($clientIp, $allowedIps, true)) {
            return new JsonResponse([
                'status' => 'error',
                'message' => sprintf('IP %s is not allowed.', $clientIp),
            ], 403);
        }

        return $next($request);
    }

    private function clientIp(Request $request): string
    {
        $forwardedFor = $request->header('X-Forwarded-For');

        if (is_string($forwardedFor) && $forwardedFor !== '') {
            $parts = explode(',', $forwardedFor);
            return trim($parts[0]);
        }

        return (string) $request->ip();
    }
}
