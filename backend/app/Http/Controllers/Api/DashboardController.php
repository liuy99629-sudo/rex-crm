<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Services\PipelineService;
use Illuminate\Http\JsonResponse;

class DashboardController extends Controller
{
    public function __invoke(PipelineService $pipeline): JsonResponse
    {
        return response()->json(['data' => $pipeline->stats()]);
    }
}
