<?php

use App\Http\Controllers\Api\V1\CsvUploadController;
use Illuminate\Support\Facades\Route;

Route::prefix('v1')
    ->middleware(['api.key', 'ip.whitelist'])
    ->group(function (): void {
        Route::post('/upload-csv', [CsvUploadController::class, 'store']);
    });
