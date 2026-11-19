<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Market and performance insights built nightly by the Spark job in analytics/ (tables analytics_*).
 * Read-only here: the job owns these tables. Before its first run the page says so.
 */
class InsightsController extends Controller
{
    public function __invoke(): JsonResponse
    {
        if (! Schema::hasTable('analytics_run_info')) {
            return response()->json(['available' => false]);
        }

        $run = DB::table('analytics_run_info')->orderByDesc('finished_at')->first();

        return response()->json([
            'available' => true,
            // The job writes UTC; the column may or may not carry an offset depending on the writer.
            // Read it as UTC unless it says otherwise, and return ISO 8601.
            'refreshed_at' => $run?->finished_at ? Carbon::parse($run->finished_at, 'UTC')->utc()->toIso8601String() : null,
            'suburb_market' => $this->rows('analytics_suburb_market', fn ($q) => $q->orderByDesc('on_market')->orderBy('suburb')),
            'lead_funnel' => $this->rows('analytics_lead_funnel', fn ($q) => $q->orderByDesc('deals')),
            // Last 12 months, newest first.
            'agent_performance' => $this->rows('analytics_agent_performance', fn ($q) => $q->orderByDesc('month')->orderBy('agent')->limit(48)),
            'stage_velocity' => $this->rows('analytics_stage_velocity'),
        ]);
    }

    private function rows(string $table, ?callable $query = null): array
    {
        if (! Schema::hasTable($table)) {
            return [];
        }
        $q = DB::table($table);

        return ($query ? $query($q) : $q)->get()->all();
    }
}
