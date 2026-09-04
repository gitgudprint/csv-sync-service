<?php

return [
    'api_key' => env('CSV_SYNC_API_KEY', ''),

    'allowed_ips' => array_values(array_filter(array_map(
        'trim',
        explode(',', env('CSV_SYNC_ALLOWED_IPS', ''))
    ))),

    'upload_root' => env('CSV_SYNC_UPLOAD_ROOT', storage_path('app/csv')),

    'default_upload_directory' => env('CSV_SYNC_DEFAULT_UPLOAD_DIRECTORY', 'csv'),
];
