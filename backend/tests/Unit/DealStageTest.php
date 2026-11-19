<?php

namespace Tests\Unit;

use App\Enums\DealStage;
use PHPUnit\Framework\TestCase;

class DealStageTest extends TestCase
{
    public function test_pipeline_order_is_stable(): void
    {
        $this->assertSame(
            ['lead', 'contacted', 'inspection', 'offer', 'negotiation', 'won', 'lost'],
            DealStage::values()
        );
    }

    public function test_only_won_and_lost_are_closed(): void
    {
        $this->assertTrue(DealStage::Won->isClosed());
        $this->assertTrue(DealStage::Lost->isClosed());
        $this->assertSame(['lead', 'contacted', 'inspection', 'offer', 'negotiation'], DealStage::openValues());
    }

    public function test_every_stage_has_a_label(): void
    {
        foreach (DealStage::cases() as $stage) {
            $this->assertNotSame('', $stage->label());
        }
    }
}
