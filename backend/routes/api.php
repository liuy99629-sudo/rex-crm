<?php

use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\ContactController;
use App\Http\Controllers\Api\DashboardController;
use App\Http\Controllers\Api\DealController;
use App\Http\Controllers\Api\HealthController;
use App\Http\Controllers\Api\IntegrationLeadController;
use App\Http\Controllers\Api\PipelineController;
use App\Http\Controllers\Api\PropertyController;
use App\Http\Controllers\Api\PublicEnquiryController;
use App\Http\Controllers\Api\PublicListingController;
use Illuminate\Support\Facades\Route;

// Liveness / readiness probe target for Kubernetes and docker compose.
Route::get('/health', HealthController::class);

Route::post('/auth/login', [AuthController::class, 'login'])->middleware('throttle:10,1');

// Public website (no login): listings on the market, and enquiries that land in the CRM as leads.
Route::prefix('public')->group(function () {
    Route::get('/listings', [PublicListingController::class, 'index'])->middleware('throttle:120,1');
    Route::get('/listings/{id}', [PublicListingController::class, 'show'])->whereNumber('id')->middleware('throttle:120,1');
    Route::post('/enquiries', [PublicEnquiryController::class, 'store'])->middleware('throttle:5,1');
});

// Machine integrations (e.g. the AWS email lead pipeline): limited tokens from `php artisan rex:integration-token`.
Route::middleware(['auth:sanctum', 'abilities:leads:write', 'throttle:120,1'])->group(function () {
    Route::post('/integrations/leads', [IntegrationLeadController::class, 'store']);
});

// The CRM itself: full-access tokens from /auth/login only (integration tokens get 403).
Route::middleware(['auth:sanctum', 'full-token'])->group(function () {
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
