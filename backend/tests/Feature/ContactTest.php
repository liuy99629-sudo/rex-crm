<?php

namespace Tests\Feature;

use App\Models\Contact;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Sanctum\Sanctum;
use Tests\TestCase;

class ContactTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        Sanctum::actingAs(User::factory()->create());
    }

    public function test_can_create_and_list_contacts(): void
    {
        $this->postJson('/api/contacts', [
            'name' => 'Jane Buyer',
            'email' => 'jane@example.com',
            'type' => 'buyer',
            'budget_min' => 800000,
            'budget_max' => 1200000,
        ])->assertCreated()->assertJsonPath('name', 'Jane Buyer');

        $this->getJson('/api/contacts')
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.type', 'buyer');
    }

    public function test_validates_contact_payload(): void
    {
        $this->postJson('/api/contacts', ['name' => '', 'type' => 'alien'])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['name', 'type']);
    }

    public function test_search_filters_by_name(): void
    {
        Contact::factory()->create(['name' => 'Alice Wong']);
        Contact::factory()->create(['name' => 'Bob Smith']);

        $this->getJson('/api/contacts?q=alice')
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.name', 'Alice Wong');
    }

    public function test_can_update_and_delete_contact(): void
    {
        $contact = Contact::factory()->create();

        $this->putJson("/api/contacts/{$contact->id}", ['name' => 'Renamed', 'type' => 'seller'])
            ->assertOk()
            ->assertJsonPath('name', 'Renamed');

        $this->deleteJson("/api/contacts/{$contact->id}")->assertNoContent();
        $this->assertModelMissing($contact);
    }
}
