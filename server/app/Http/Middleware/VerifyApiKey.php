<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class VerifyApiKey
{
    public function handle(Request $request, Closure $next): mixed
    {
        $configuredApiKey = (string) config('csv_sync.api_key', '');

        if ($configuredApiKey === '') {
            return new JsonResponse([
                'status' => 'error',
                'message' => 'Server API key is not configured.',
            ], 500);
        }

        $incomingApiKey = (string) $request->header('X-API-Key', '');

        if ($incomingApiKey === '' || !hash_equals($configuredApiKey, $incomingApiKey)) {
            return new JsonResponse([
                'status' => 'error',
                'message' => 'Invalid API key.',
            ], 401);
        }

        return $next($request);
    }
}
