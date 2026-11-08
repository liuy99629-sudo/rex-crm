<?php

use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\ContactController;
use App\Http\Controllers\Api\DashboardController;
use App\Http\Controllers\Api\DealController;
use App\Http\Controllers\Api\HealthController;
use App\Http\Controllers\Api\PipelineController;
use App\Http\Controllers\Api\PropertyController;
use Illuminate\Support\Facades\Route;

// Liveness / readiness probe target for Kubernetes and docker compose.
Route::get('/health', HealthController::class);

Route::post('/auth/login', [AuthController::class, 'login'])->middleware('throttle:10,1');

Route::middleware('auth:sanctum')->group(function () {
    Route::get('/auth/me', [AuthController::class, 'me']);
    Route::post('/auth/logout', [AuthController::class, 'logout']);

    Route::get('/dashboard', DashboardController::class);
    Route::get('/pipeline', [PipelineController::class, 'index']);

    Route::apiResource('contacts', ContactController::class);
    Route::apiResource('properties', PropertyController::class);
    Route::apiResource('deals', DealController::class);
    Route::patch('/deals/{deal}/stage', [DealController::class, 'updateStage']);
    Route::post('/deals/{deal}/notes', [DealController::class, 'addNote']);
});
