<?php

namespace Database\Factories;

use App\Enums\ContactType;
use App\Models\Contact;
use Illuminate\Database\Eloquent\Factories\Factory;

/** @extends Factory<Contact> */
class ContactFactory extends Factory
{
    protected $model = Contact::class;

    public function definition(): array
    {
        $min = fake()->randomElement([400, 600, 800, 1000, 1500]) * 1000;

        return [
            'user_id' => null,
            'name' => fake()->name(),
            'email' => fake()->unique()->safeEmail(),
            'phone' => '04'.fake()->numerify('## ### ###'),
            'type' => fake()->randomElement(ContactType::values()),
            'source' => fake()->randomElement(['Domain', 'realestate.com.au', 'Referral', 'Open home', 'Walk-in']),
            'budget_min' => $min,
            'budget_max' => $min + fake()->randomElement([200, 400, 600]) * 1000,
            'notes' => fake()->boolean(40) ? fake()->sentence() : null,
        ];
    }
}
