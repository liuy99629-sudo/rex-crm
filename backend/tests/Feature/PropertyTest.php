<?php

namespace Tests\Feature;

use App\Models\Property;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Sanctum\Sanctum;
use Tests\TestCase;

class PropertyTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        Sanctum::actingAs(User::factory()->create());
    }

    public function test_can_create_property(): void
    {
        $this->postJson('/api/properties', [
            'title' => '3 bed house',
            'address_line' => '12 Smith St',
            'suburb' => 'Parramatta',
            'state' => 'NSW',
            'postcode' => '2150',
            'type' => 'house',
            'status' => 'active',
            'price' => 1250000,
        ])->assertCreated()->assertJsonPath('status', 'active');
    }

    public function test_rejects_invalid_postcode(): void
    {
        $this->postJson('/api/properties', [
            'title' => 'x', 'address_line' => 'x', 'suburb' => 'x',
            'state' => 'NSW', 'postcode' => '12', 'type' => 'house', 'status' => 'active',
        ])->assertStatus(422)->assertJsonValidationErrors('postcode');
    }

    public function test_filters_by_status_and_price(): void
    {
        Property::factory()->create(['status' => 'active', 'price' => 900000]);
        Property::factory()->create(['status' => 'sold', 'price' => 900000]);
        Property::factory()->create(['status' => 'active', 'price' => 2000000]);

        $this->getJson('/api/properties?status=active&max_price=1000000')
            ->assertOk()
            ->assertJsonCount(1, 'data');
    }
}
