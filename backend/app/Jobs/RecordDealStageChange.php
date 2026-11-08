<?php

namespace App\Jobs;

use App\Enums\DealStage;
use App\Enums\PropertyStatus;
use App\Models\Deal;
use App\Models\DealActivity;
use App\Services\PipelineService;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;

/**
 * Runs on the queue worker (Redis -> Worker -> PostgreSQL in the architecture diagram).
 * The API responds immediately after changing the stage; this job does the follow-up writes.
 */
class RecordDealStageChange implements ShouldQueue
{
    use Queueable;

    public int $tries = 3;

    public function __construct(
        public int $dealId,
        public string $from,
        public string $to,
        public ?int $userId = null,
    ) {}

    public function handle(PipelineService $pipeline): void
    {
        $deal = Deal::with('property')->find($this->dealId);

        if (! $deal) {
            return; // deal was deleted before the job ran
        }

        $fromLabel = DealStage::tryFrom($this->from)?->label() ?? $this->from;
        $toLabel = DealStage::tryFrom($this->to)?->label() ?? $this->to;

        DealActivity::create([
            'deal_id' => $deal->id,
            'user_id' => $this->userId,
            'type' => 'stage_change',
            'body' => "Stage changed from {$fromLabel} to {$toLabel}",
            'meta' => ['from' => $this->from, 'to' => $this->to],
        ]);

        // A won deal means the linked listing has been sold.
        if ($this->to === DealStage::Won->value && $deal->property) {
            $deal->property->update(['status' => PropertyStatus::Sold]);
        }

        $pipeline->flush();
    }
}
