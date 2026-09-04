<?php

use App\Http\Controllers\Api\V1\CsvUploadController;
use Illuminate\Support\Facades\Route;

Route::prefix('v1')
    ->middleware(['api.key', 'ip.whitelist'])
    ->group(function (): void {
        Route::get('/list-csv', [CsvUploadController::class, 'list']);
        Route::post('/upload-csv', [CsvUploadController::class, 'store']);
    });
