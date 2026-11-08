<?php

namespace App\Providers;

use App\Services\PipelineService;
use Illuminate\Http\Resources\Json\JsonResource;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(PipelineService::class);
    }

    public function boot(): void
    {
        // Single resources are returned unwrapped; paginated lists keep Laravel's {data, links, meta} envelope.
        JsonResource::withoutWrapping();
    }
}
