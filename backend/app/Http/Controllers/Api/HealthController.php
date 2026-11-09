<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;

/** Liveness target for Kubernetes / docker compose. Deliberately touches no database. */
class HealthController extends Controller
{
    public function __invoke(): JsonResponse
    {
        return response()->json(['name' => config('app.name'), 'status' => 'ok']);
    }
}
