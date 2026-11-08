<?php

namespace Database\Factories;

use App\Enums\DealStage;
use App\Models\Contact;
use App\Models\Deal;
use Illuminate\Database\Eloquent\Factories\Factory;

/** @extends Factory<Deal> */
class DealFactory extends Factory
{
    protected $model = Deal::class;

    public function definition(): array
    {
        return [
            'title' => fake()->randomElement(['Purchase', 'Sale listing', 'Investment enquiry', 'Rental placement']).' - '.fake()->lastName(),
            'contact_id' => Contact::factory(),
            'property_id' => null,
            'user_id' => null,
            'stage' => DealStage::Lead->value,
            'value' => fake()->numberBetween(40, 250) * 10000,
            'expected_close_date' => fake()->dateTimeBetween('now', '+90 days')->format('Y-m-d'),
            'notes' => null,
        ];
    }

    public function stage(DealStage $stage): static
    {
        return $this->state(fn () => [
            'stage' => $stage->value,
            'closed_at' => $stage->isClosed() ? now() : null,
        ]);
    }
}
