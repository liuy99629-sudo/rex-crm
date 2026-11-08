<?php

namespace Database\Factories;

use App\Enums\PropertyStatus;
use App\Enums\PropertyType;
use App\Models\Property;
use Illuminate\Database\Eloquent\Factories\Factory;

/** @extends Factory<Property> */
class PropertyFactory extends Factory
{
    protected $model = Property::class;

    public function definition(): array
    {
        $suburb = fake()->randomElement(['Parramatta', 'Chatswood', 'Bondi', 'Surry Hills', 'Strathfield', 'Burwood', 'Epping', 'Hurstville']);
        $number = fake()->numberBetween(1, 220);
        $street = fake()->randomElement(['George St', 'Victoria Rd', 'Park Ave', 'Church St', 'Station St', 'Elizabeth St']);

        return [
            'user_id' => null,
            'owner_id' => null,
            'title' => fake()->randomElement(['Modern family home', 'Stylish apartment', 'Renovated townhouse', 'Prime development site', 'Light-filled residence']).' in '.$suburb,
            'address_line' => "{$number} {$street}",
            'suburb' => $suburb,
            'state' => 'NSW',
            'postcode' => (string) fake()->numberBetween(2000, 2250),
            'type' => fake()->randomElement(PropertyType::values()),
            'status' => fake()->randomElement([PropertyStatus::Active->value, PropertyStatus::Active->value, PropertyStatus::Draft->value, PropertyStatus::UnderOffer->value]),
            'price' => fake()->numberBetween(55, 360) * 10000,
            'bedrooms' => fake()->numberBetween(1, 5),
            'bathrooms' => fake()->numberBetween(1, 3),
            'parking' => fake()->numberBetween(0, 3),
            'land_size_sqm' => fake()->numberBetween(80, 900),
            'description' => fake()->paragraph(),
            'listed_at' => fake()->dateTimeBetween('-60 days', 'now')->format('Y-m-d'),
        ];
    }
}
