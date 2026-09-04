<?php

namespace App\Services;

class ChecksumService
{
    public function sha256FromFile(string $path): string
    {
        return hash_file('sha256', $path);
    }
}
