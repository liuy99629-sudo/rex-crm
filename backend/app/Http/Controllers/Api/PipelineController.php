<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Services\PipelineService;
use Illuminate\Http\JsonResponse;

class PipelineController extends Controller
{
    public function __construct(private readonly PipelineService $pipeline) {}

    public function index(): JsonResponse
    {
        return response()->json(['data' => $this->pipeline->board()]);
    }
}
