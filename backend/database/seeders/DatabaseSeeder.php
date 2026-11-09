<?php

namespace Database\Seeders;

use App\Enums\DealStage;
use App\Models\Contact;
use App\Models\Deal;
use App\Models\Property;
use App\Models\User;
use Illuminate\Database\Seeder;

class DatabaseSeeder extends Seeder
{
    /**
     * Demo data. Login: admin@rexcrm.test / password
     */
    public function run(): void
    {
        // Safe to re-run (README says to seed after `docker compose up`, and the pgdata volume persists).
        if (User::where('email', 'admin@rexcrm.test')->exists()) {
            $this->command?->info('Demo data already present, skipping.');

            return;
        }

        $admin = User::factory()->admin()->create([
            'name' => 'Demo Admin',
            'email' => 'admin@rexcrm.test',
        ]);
        $agent = User::factory()->create([
            'name' => 'Demo Agent',
            'email' => 'agent@rexcrm.test',
        ]);
        $agents = [$admin, $agent];

        $contacts = collect(range(1, 16))->map(
            fn () => Contact::factory()->create(['user_id' => fake()->randomElement($agents)->id])
        );

        $properties = collect(range(1, 12))->map(
            fn () => Property::factory()->create([
                'user_id' => fake()->randomElement($agents)->id,
                'owner_id' => $contacts->random()->id,
            ])
        );

        $stages = DealStage::cases();

        foreach (range(1, 22) as $i) {
            $stage = $stages[$i % count($stages)];

            Deal::factory()->stage($stage)->create([
                'contact_id' => $contacts->random()->id,
                'property_id' => fake()->boolean(70) ? $properties->random()->id : null,
                'user_id' => fake()->randomElement($agents)->id,
            ]);
        }
    }
}
