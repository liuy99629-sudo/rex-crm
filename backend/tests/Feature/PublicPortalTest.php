<?php

namespace Tests\Feature;

use App\Models\Contact;
use App\Models\Deal;
use App\Models\Property;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Cache;
use Tests\TestCase;

class PublicPortalTest extends TestCase
{
    use RefreshDatabase;

    private function listing(array $attrs = []): Property
    {
        return Property::factory()->create($attrs + ['status' => 'active']);
    }

    private function enquiry(array $overrides = []): array
    {
        return $overrides + [
            'name' => 'Jane Visitor',
            'email' => 'jane@example.com',
            'phone' => '0400 000 000',
            'message' => 'Is the pool heated?',
        ];
    }

    public function test_lists_only_properties_on_the_market_without_login(): void
    {
        $active = $this->listing(['title' => 'On the market']);
        $this->listing(['status' => 'under_offer', 'title' => 'Under offer']);
        foreach (['draft', 'sold', 'withdrawn'] as $status) {
            $this->listing(['status' => $status]);
        }

        $res = $this->getJson('/api/public/listings')->assertOk()->assertJsonCount(2, 'data');

        $this->assertEqualsCanonicalizing(['On the market', 'Under offer'], array_column($res->json('data'), 'title'));
        $this->getJson("/api/public/listings/{$active->id}")->assertOk()->assertJsonPath('title', 'On the market');
    }

    public function test_hides_vendor_and_internal_fields(): void
    {
        $owner = Contact::factory()->create(['name' => 'Secret Vendor']);
        $listing = $this->listing(['owner_id' => $owner->id, 'user_id' => User::factory()->create(['name' => 'Agent Amy'])->id]);

        $res = $this->getJson("/api/public/listings/{$listing->id}")->assertOk();

        $res->assertJsonPath('agent_name', 'Agent Amy');
        $this->assertArrayNotHasKey('owner', $res->json());
        $this->assertArrayNotHasKey('owner_id', $res->json());
        $this->assertArrayNotHasKey('user_id', $res->json());
        $this->assertStringNotContainsString('Secret Vendor', $res->getContent());
    }

    public function test_draft_or_sold_listing_is_not_found(): void
    {
        $this->getJson('/api/public/listings/'.$this->listing(['status' => 'sold'])->id)->assertNotFound();
        $this->getJson('/api/public/listings/'.$this->listing(['status' => 'draft'])->id)->assertNotFound();
    }

    public function test_filters(): void
    {
        $this->listing(['suburb' => 'Epping', 'type' => 'house', 'price' => 1_800_000, 'bedrooms' => 4]);
        $this->listing(['suburb' => 'Epping', 'type' => 'apartment', 'price' => 900_000, 'bedrooms' => 2]);
        $this->listing(['suburb' => 'Bondi', 'type' => 'house', 'price' => 2_500_000, 'bedrooms' => 3]);

        $this->getJson('/api/public/listings?suburb=epping')->assertJsonCount(2, 'data');
        $this->getJson('/api/public/listings?type=house&max_price=2000000')->assertJsonCount(1, 'data');
        $this->getJson('/api/public/listings?min_bedrooms=3')->assertJsonCount(2, 'data');
        $this->getJson('/api/public/listings?type=castle')->assertStatus(422);
    }

    public function test_enquiry_creates_contact_lead_and_note_for_the_listing_agent(): void
    {
        $agent = User::factory()->create();
        $listing = $this->listing(['user_id' => $agent->id, 'price' => 1_250_000]);

        $this->postJson('/api/public/enquiries', $this->enquiry(['listing_id' => $listing->id]))
            ->assertCreated()
            ->assertJsonStructure(['reference', 'message']);

        $contact = Contact::where('email', 'jane@example.com')->sole();
        $this->assertSame('Website', $contact->source);
        $this->assertSame('buyer', $contact->type->value);
        $deal = Deal::where('contact_id', $contact->id)->sole();
        $this->assertSame('lead', $deal->stage->value);
        $this->assertSame($listing->id, $deal->property_id);
        $this->assertSame($agent->id, $deal->user_id);
        $this->assertSame(1_250_000, $deal->value);
        $this->assertStringContainsString('Is the pool heated?', $deal->activities()->sole()->body);
    }

    public function test_repeat_enquiry_reuses_contact_and_open_deal(): void
    {
        $listing = $this->listing();
        Contact::factory()->create(['email' => 'JANE@example.com', 'name' => 'Jane Existing']);

        $this->postJson('/api/public/enquiries', $this->enquiry(['listing_id' => $listing->id]))->assertCreated();
        $this->postJson('/api/public/enquiries', $this->enquiry(['listing_id' => $listing->id, 'message' => 'Any update?']))->assertCreated();

        $this->assertSame(1, Contact::count());
        $this->assertSame(1, Deal::count());
        $this->assertSame(2, Deal::first()->activities()->count());
    }

    public function test_enquiry_flushes_the_pipeline_cache(): void
    {
        $listing = $this->listing();
        $this->getJson('/api/public/listings'); // unrelated warm-up
        Cache::put('dashboard:stats', ['stale' => true], 60);

        $this->postJson('/api/public/enquiries', $this->enquiry(['listing_id' => $listing->id]))->assertCreated();

        $this->assertNull(Cache::get('dashboard:stats'));
    }

    public function test_enquiry_validation_honeypot_and_hidden_listings(): void
    {
        $listing = $this->listing();

        $this->postJson('/api/public/enquiries', ['listing_id' => $listing->id])->assertStatus(422)
            ->assertJsonValidationErrors(['name', 'email', 'message']);
        $this->postJson('/api/public/enquiries', $this->enquiry(['listing_id' => $listing->id, 'website' => 'http://spam.example']))
            ->assertStatus(422);
        $this->postJson('/api/public/enquiries', $this->enquiry(['listing_id' => $this->listing(['status' => 'sold'])->id]))
            ->assertNotFound();
        $this->assertSame(0, Deal::count());
    }

    public function test_enquiries_are_rate_limited_per_visitor(): void
    {
        $listing = $this->listing();
        foreach (range(1, 5) as $i) {
            $this->postJson('/api/public/enquiries', $this->enquiry(['listing_id' => $listing->id]))->assertCreated();
        }

        $this->postJson('/api/public/enquiries', $this->enquiry(['listing_id' => $listing->id]))->assertStatus(429);
        // A different visitor (forwarded by the portal/gateway) is not blocked.
        $this->withHeader('X-Forwarded-For', '203.0.113.9')
            ->postJson('/api/public/enquiries', $this->enquiry(['listing_id' => $listing->id]))->assertCreated();
    }
}
