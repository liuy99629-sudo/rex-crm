<?php

namespace Tests\Feature;

use App\Enums\DealStage;
use App\Jobs\RecordDealStageChange;
use App\Models\Contact;
use App\Models\Deal;
use App\Models\Property;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Queue;
use Laravel\Sanctum\Sanctum;
use Tests\TestCase;

class DealPipelineTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = User::factory()->create();
        Sanctum::actingAs($this->user);
    }

    public function test_can_create_deal_defaulting_to_lead_stage(): void
    {
        $contact = Contact::factory()->create();

        $this->postJson('/api/deals', [
            'title' => 'Purchase - Smith',
            'contact_id' => $contact->id,
            'value' => 950000,
        ])->assertCreated()
            ->assertJsonPath('stage', 'lead')
            ->assertJsonPath('user_id', $this->user->id);
    }

    public function test_pipeline_board_groups_deals_by_every_stage(): void
    {
        Deal::factory()->stage(DealStage::Lead)->create(['value' => 100]);
        Deal::factory()->stage(DealStage::Lead)->create(['value' => 200]);
        Deal::factory()->stage(DealStage::Offer)->create(['value' => 500]);

        $response = $this->getJson('/api/pipeline')->assertOk();

        $board = collect($response->json('data'))->keyBy('stage');

        $this->assertCount(count(DealStage::cases()), $board);
        $this->assertSame(2, $board['lead']['count']);
        $this->assertSame(300, $board['lead']['total_value']);
        $this->assertSame(1, $board['offer']['count']);
        $this->assertSame(0, $board['won']['count']);
    }

    public function test_changing_stage_saves_immediately_and_queues_follow_up_job(): void
    {
        Queue::fake();
        $deal = Deal::factory()->create();

        $this->patchJson("/api/deals/{$deal->id}/stage", ['stage' => 'inspection'])
            ->assertOk()
            ->assertJsonPath('stage', 'inspection');

        $this->assertSame(DealStage::Inspection, $deal->fresh()->stage);

        Queue::assertPushed(
            RecordDealStageChange::class,
            fn (RecordDealStageChange $job) => $job->dealId === $deal->id
                && $job->from === 'lead'
                && $job->to === 'inspection'
        );
    }

    public function test_same_stage_does_not_queue_a_job(): void
    {
        Queue::fake();
        $deal = Deal::factory()->create();

        $this->patchJson("/api/deals/{$deal->id}/stage", ['stage' => 'lead'])->assertOk();

        Queue::assertNothingPushed();
    }

    public function test_rejects_unknown_stage(): void
    {
        $deal = Deal::factory()->create();

        $this->patchJson("/api/deals/{$deal->id}/stage", ['stage' => 'banana'])
            ->assertStatus(422)
            ->assertJsonValidationErrors('stage');
    }

    public function test_worker_job_logs_activity_and_marks_property_sold_when_won(): void
    {
        $property = Property::factory()->create(['status' => 'under_offer']);
        $deal = Deal::factory()->create(['property_id' => $property->id]);

        // queue connection is "sync" in tests, so the job runs inline.
        $this->patchJson("/api/deals/{$deal->id}/stage", ['stage' => 'won'])->assertOk();

        $this->assertDatabaseHas('deal_activities', [
            'deal_id' => $deal->id,
            'type' => 'stage_change',
        ]);
        $this->assertSame('sold', $property->fresh()->status->value);
        $this->assertNotNull($deal->fresh()->closed_at);
    }

    public function test_can_add_note_and_see_it_on_deal(): void
    {
        $deal = Deal::factory()->create();

        $this->postJson("/api/deals/{$deal->id}/notes", ['body' => 'Called the buyer'])
            ->assertCreated()
            ->assertJsonPath('type', 'note');

        $this->getJson("/api/deals/{$deal->id}")
            ->assertOk()
            ->assertJsonCount(1, 'activities');
    }

    public function test_can_delete_a_note(): void
    {
        $deal = Deal::factory()->create();
        $note = $deal->activities()->create(['user_id' => $this->user->id, 'type' => 'note', 'body' => 'Typo']);

        $this->deleteJson("/api/deals/{$deal->id}/notes/{$note->id}")->assertNoContent();

        $this->assertDatabaseMissing('deal_activities', ['id' => $note->id]);
    }

    public function test_cannot_delete_stage_change_entry_or_another_deals_note(): void
    {
        $deal = Deal::factory()->create();
        $other = Deal::factory()->create();
        $stageChange = $deal->activities()->create(['type' => 'stage_change', 'body' => 'Stage changed from Lead to Offer']);
        $otherNote = $other->activities()->create(['type' => 'note', 'body' => 'Not yours']);

        $this->deleteJson("/api/deals/{$deal->id}/notes/{$stageChange->id}")->assertForbidden();
        $this->deleteJson("/api/deals/{$deal->id}/notes/{$otherNote->id}")->assertNotFound();

        $this->assertDatabaseCount('deal_activities', 2);
    }

    public function test_deleting_contact_refreshes_cached_dashboard_and_board(): void
    {
        $contact = Contact::factory()->create();
        Deal::factory()->stage(DealStage::Lead)->create(['contact_id' => $contact->id, 'value' => 1000]);

        // Warm the caches.
        $this->getJson('/api/dashboard')->assertJsonPath('data.open_deals', 1);
        $this->getJson('/api/pipeline')->assertOk();

        // Its deals are removed by the database cascade, so no Deal event fires.
        $this->deleteJson("/api/contacts/{$contact->id}")->assertNoContent();

        $this->getJson('/api/dashboard')
            ->assertJsonPath('data.contacts', 0)
            ->assertJsonPath('data.open_deals', 0)
            ->assertJsonPath('data.pipeline_value', 0);
        $lead = collect($this->getJson('/api/pipeline')->json('data'))->firstWhere('stage', 'lead');
        $this->assertSame(0, $lead['count']);
    }

    public function test_property_status_change_refreshes_cached_dashboard(): void
    {
        $property = Property::factory()->create(['status' => 'active']);

        $this->getJson('/api/dashboard')->assertJsonPath('data.active_listings', 1);

        $property->update(['status' => 'withdrawn']);

        $this->getJson('/api/dashboard')->assertJsonPath('data.active_listings', 0);
    }

    public function test_dashboard_stats(): void
    {
        Deal::factory()->stage(DealStage::Lead)->create(['value' => 1000]);
        Deal::factory()->stage(DealStage::Won)->create(['value' => 5000]);

        $this->getJson('/api/dashboard')
            ->assertOk()
            ->assertJsonPath('data.open_deals', 1)
            ->assertJsonPath('data.pipeline_value', 1000)
            ->assertJsonPath('data.won_this_month', 1)
            ->assertJsonPath('data.won_value_this_month', 5000);
    }
}
