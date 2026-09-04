<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Services\ChecksumService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

class CsvUploadController extends Controller
{
    public function __construct(private readonly ChecksumService $checksumService)
    {
    }

    public function list(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'directory' => ['nullable', 'string', 'max:120', 'regex:/^[A-Za-z0-9_\/-]+$/'],
        ]);

        $uploadRoot = (string) config('csv_sync.upload_root');
        $defaultDirectory = (string) config('csv_sync.default_upload_directory', 'csv');
        $relativeDirectory = trim((string) ($validated['directory'] ?? $defaultDirectory), '/\\');
        $relativeDirectory = $relativeDirectory !== '' ? $relativeDirectory : $defaultDirectory;

        $resolvedRoot = realpath($uploadRoot);
        if ($resolvedRoot === false) {
            return response()->json([
                'status' => 'error',
                'message' => 'Upload root directory is invalid.',
            ], 500);
        }

        $targetDirectory = $resolvedRoot.DIRECTORY_SEPARATOR.$relativeDirectory;
        $resolvedTargetDirectory = realpath($targetDirectory);

        if ($resolvedTargetDirectory === false || !Str::startsWith($resolvedTargetDirectory, $resolvedRoot)) {
            return response()->json([
                'status' => 'error',
                'message' => 'Target directory is outside allowed upload root.',
            ], 400);
        }

        if (!is_dir($resolvedTargetDirectory)) {
            return response()->json([
                'status' => 'ok',
                'directory' => $relativeDirectory,
                'files' => [],
                'message' => 'Directory does not exist yet.',
            ], 200);
        }

        $files = [];
        $csvFiles = glob($resolvedTargetDirectory.DIRECTORY_SEPARATOR.'*.csv');
        
        if ($csvFiles !== false) {
            foreach ($csvFiles as $filePath) {
                if (is_file($filePath)) {
                    $files[] = [
                        'filename' => basename($filePath),
                        'size' => (int) filesize($filePath),
                        'sha256' => $this->checksumService->sha256FromFile($filePath),
                        'modified' => (int) filemtime($filePath),
                    ];
                }
            }
        }

        usort($files, static fn ($a, $b) => strcmp($a['filename'], $b['filename']));

        return response()->json([
            'status' => 'ok',
            'directory' => $relativeDirectory,
            'files' => $files,
            'count' => count($files),
        ], 200);
    }

    public function store(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'file' => ['required', 'file', 'mimes:csv,txt'],
            'directory' => ['nullable', 'string', 'max:120', 'regex:/^[A-Za-z0-9_\/-]+$/'],
        ]);

        $uploadedFile = $request->file('file');
        if ($uploadedFile === null) {
            return response()->json([
                'status' => 'error',
                'message' => 'File field is required.',
            ], 400);
        }

        $originalName = (string) $uploadedFile->getClientOriginalName();
        $safeName = basename($originalName);

        if ($safeName !== $originalName || $safeName === '' || $safeName === '.' || $safeName === '..') {
            return response()->json([
                'status' => 'error',
                'message' => 'Invalid filename: path traversal is not allowed.',
            ], 400);
        }

        if (!Str::endsWith(Str::lower($safeName), '.csv')) {
            return response()->json([
                'status' => 'error',
                'message' => 'Only .csv files are allowed.',
            ], 400);
        }

        $uploadRoot = (string) config('csv_sync.upload_root');
        $defaultDirectory = (string) config('csv_sync.default_upload_directory', 'csv');
        $relativeDirectory = trim((string) ($validated['directory'] ?? $defaultDirectory), '/\\');
        $relativeDirectory = $relativeDirectory !== '' ? $relativeDirectory : $defaultDirectory;

        if (!is_dir($uploadRoot) && !mkdir($uploadRoot, 0755, true) && !is_dir($uploadRoot)) {
            return response()->json([
                'status' => 'error',
                'message' => 'Unable to create upload root directory.',
            ], 500);
        }

        $resolvedRoot = realpath($uploadRoot);
        if ($resolvedRoot === false) {
            return response()->json([
                'status' => 'error',
                'message' => 'Upload root directory is invalid.',
            ], 500);
        }

        $targetDirectory = $resolvedRoot.DIRECTORY_SEPARATOR.$relativeDirectory;

        if (!is_dir($targetDirectory) && !mkdir($targetDirectory, 0755, true) && !is_dir($targetDirectory)) {
            return response()->json([
                'status' => 'error',
                'message' => 'Unable to create target upload directory.',
            ], 500);
        }

        $resolvedTargetDirectory = realpath($targetDirectory);
        if ($resolvedTargetDirectory === false || !Str::startsWith($resolvedTargetDirectory, $resolvedRoot)) {
            return response()->json([
                'status' => 'error',
                'message' => 'Target directory is outside allowed upload root.',
            ], 400);
        }

        $incomingSha256 = $this->checksumService->sha256FromFile($uploadedFile->getRealPath());
        $destinationPath = $resolvedTargetDirectory.DIRECTORY_SEPARATOR.$safeName;

        if (is_file($destinationPath)) {
            $existingSha256 = $this->checksumService->sha256FromFile($destinationPath);

            if (hash_equals($existingSha256, $incomingSha256)) {
                return response()->json([
                    'status' => 'already_exists',
                    'filename' => $safeName,
                    'size' => (int) $uploadedFile->getSize(),
                    'sha256' => $incomingSha256,
                    'message' => 'File already exists and checksum matches.',
                ], 200);
            }

            return response()->json([
                'status' => 'conflict',
                'filename' => $safeName,
                'existing_sha256' => $existingSha256,
                'incoming_sha256' => $incomingSha256,
                'message' => 'A file with the same name but different checksum already exists.',
            ], 409);
        }

        $uploadedFile->move($resolvedTargetDirectory, $safeName);
        $storedPath = $resolvedTargetDirectory.DIRECTORY_SEPARATOR.$safeName;

        return response()->json([
            'status' => 'success',
            'filename' => $safeName,
            'size' => (int) filesize($storedPath),
            'sha256' => $incomingSha256,
        ], 200);
    }
}
