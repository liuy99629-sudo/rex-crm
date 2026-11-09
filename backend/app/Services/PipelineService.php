<?php

namespace App\Services;

use App\Enums\DealStage;
use App\Http\Resources\DealResource;
use App\Models\Contact;
use App\Models\Deal;
use App\Models\Property;
use Illuminate\Support\Facades\Cache;

/**
 * Builds the sales pipeline board and dashboard numbers.
 * Results are cached in Redis and invalidated whenever a deal changes.
 */
class PipelineService
{
    public const BOARD_KEY = 'pipeline:board';

    public const STATS_KEY = 'dashboard:stats';

    /** @return list<array<string, mixed>> */
    public function board(): array
    {
        return Cache::remember(self::BOARD_KEY, now()->addMinutes(5), function () {
            $byStage = Deal::query()
                ->with(['contact:id,name', 'property:id,title,suburb', 'agent:id,name'])
                ->latest('updated_at')
                ->get()
                ->groupBy(fn (Deal $deal) => $deal->stage->value);

            return collect(DealStage::cases())->map(function (DealStage $stage) use ($byStage) {
                $deals = $byStage->get($stage->value, collect());

                return [
                    'stage' => $stage->value,
                    'label' => $stage->label(),
                    'count' => $deals->count(),
                    'total_value' => (int) $deals->sum('value'),
                    'deals' => DealResource::collection($deals)->resolve(),
                ];
            })->all();
        });
    }

    /** @return array<string, int> */
    public function stats(): array
    {
        return Cache::remember(self::STATS_KEY, now()->addMinute(), function () {
            $open = Deal::query()->whereIn('stage', DealStage::openValues());
            $wonThisMonth = Deal::query()
                ->where('stage', DealStage::Won->value)
                ->where('closed_at', '>=', now()->startOfMonth());

            return [
                'contacts' => Contact::count(),
                'active_listings' => Property::where('status', 'active')->count(),
                'open_deals' => (clone $open)->count(),
                'pipeline_value' => (int) (clone $open)->sum('value'),
                'won_this_month' => (clone $wonThisMonth)->count(),
                'won_value_this_month' => (int) (clone $wonThisMonth)->sum('value'),
            ];
        });
    }

    public function flush(): void
    {
        Cache::forget(self::BOARD_KEY);
        Cache::forget(self::STATS_KEY);
    }
}
