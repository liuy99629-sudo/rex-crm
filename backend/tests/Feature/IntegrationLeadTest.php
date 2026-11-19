<?php

namespace Tests\Feature;

use App\Models\Contact;
use App\Models\Deal;
use App\Models\Property;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Tests\TestCase;

class IntegrationLeadTest extends TestCase
{
    use RefreshDatabase;

    private string $token;

    protected function setUp(): void
    {
        parent::setUp();
        Artisan::call('rex:integration-token', ['name' => 'lead-pipeline']);
        $this->token = trim(collect(explode("\n", Artisan::output()))->filter()->last());
    }

    private function lead(array $overrides = []): array
    {
        return $overrides + [
            'source' => 'Domain',
            'external_id' => 'msg-123@mail.example',
            'name' => 'Sam Lee',
            'email' => 'sam@example.com',
            'phone' => '0412 345 678',
            'message' => 'Can I inspect on Saturday?',
            'listing_hint' => '14 Kent Street, Epping NSW 2121',
            'budget_max' => 1_900_000,
        ];
    }

    private function sendLead(array $body)
    {
        return $this->withToken($this->token)->postJson('/api/integrations/leads', $body);
    }

    public function test_lead_is_matched_to_the_listing_by_address(): void
    {
        $agent = User::factory()->create();
        $listing = Property::factory()->create(['address_line' => '14 Kent Street', 'suburb' => 'Epping', 'status' => 'active', 'user_id' => $agent->id, 'price' => 1_850_000]);
        Property::factory()->create(['address_line' => '1 Other Road', 'status' => 'active']);

        $this->sendLead($this->lead())->assertCreated()->assertJsonPath('listing_id', $listing->id);

        $deal = Deal::sole();
        $this->assertSame('Domain enquiry - Sam Lee', $deal->title);
        $this->assertSame($agent->id, $deal->user_id);
        $this->assertSame(1_850_000, $deal->value);
        $contact = Contact::sole();
        $this->assertSame('Domain', $contact->source);
        $this->assertSame(1_900_000, $contact->budget_max);
        $this->assertStringContainsString('Can I inspect on Saturday?', $deal->activities()->sole()->body);
    }

    public function test_falls_back_to_title_and_to_no_listing(): void
    {
        $listing = Property::factory()->create(['title' => 'Family home with pool in Epping', 'status' => 'active']);

        $this->sendLead($this->lead(['listing_hint' => 'Family home with pool in Epping']))->assertJsonPath('listing_id', $listing->id);
        $this->sendLead($this->lead(['email' => 'other@example.com', 'listing_hint' => 'Somewhere unknown']))
            ->assertCreated()->assertJsonPath('listing_id', null);

        $this->assertNull(Deal::where('title', 'like', '%')->latest('id')->first()->property_id);
    }

    public function test_existing_contact_keeps_agent_entered_details(): void
    {
        Contact::factory()->create(['email' => 'SAM@example.com', 'phone' => '0400 000 000', 'budget_max' => 1_000_000, 'budget_min' => null]);

        $this->sendLead($this->lead(['budget_min' => 800_000]))->assertCreated();

        $c = Contact::sole();
        $this->assertSame('0400 000 000', $c->phone);
        $this->assertSame(1_000_000, $c->budget_max); // not overwritten
        $this->assertSame(800_000, $c->budget_min); // gap filled
    }

    public function test_validation(): void
    {
        $this->sendLead(['source' => 'Domain'])->assertStatus(422)->assertJsonValidationErrors(['external_id', 'name', 'email', 'message']);
    }

    public function test_requires_an_integration_token(): void
    {
        $this->postJson('/api/integrations/leads', $this->lead())->assertUnauthorized();

        // A normal login token has every ability, so it may post leads too...
        $user = User::factory()->create();
        $this->withToken($user->createToken('web')->plainTextToken)->postJson('/api/integrations/leads', $this->lead())->assertCreated();
    }

    public function test_integration_token_cannot_use_the_rest_of_the_crm(): void
    {
        foreach (['/api/contacts', '/api/dashboard', '/api/auth/me', '/api/pipeline'] as $url) {
            $this->withToken($this->token)->getJson($url)->assertForbidden();
        }
        $contact = Contact::factory()->create();
        $this->withToken($this->token)->deleteJson("/api/contacts/{$contact->id}")->assertForbidden();
        $this->assertModelExists($contact);
    }
}
