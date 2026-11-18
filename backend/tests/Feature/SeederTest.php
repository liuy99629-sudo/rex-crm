<?php

namespace Tests\Feature;

use App\Enums\DealStage;
use App\Models\Contact;
use App\Models\Deal;
use App\Models\DealActivity;
use App\Models\Property;
use App\Models\User;
use Database\Seeders\DatabaseSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class SeederTest extends TestCase
{
    use RefreshDatabase;

    public function test_seeder_can_run_twice_without_duplicating_demo_data(): void
    {
        $this->seed(DatabaseSeeder::class);
        $this->seed(DatabaseSeeder::class);

        $this->assertSame(1, User::where('email', 'admin@rexcrm.test')->count());
        $this->assertSame(16, Contact::count());
        $this->assertSame(22, Deal::count());
    }

    public function test_demo_data_is_realistic_and_has_closed_outcomes(): void
    {
        $this->seed(DatabaseSeeder::class);

        // Closed deals carry closed_at and real outcomes (the win-probability model learns from them).
        $this->assertSame(5, Deal::where('stage', 'won')->whereNotNull('closed_at')->count());
        $this->assertSame(5, Deal::where('stage', 'lost')->whereNotNull('closed_at')->count());
        $this->assertSame(0, Deal::whereIn('stage', DealStage::openValues())->whereNotNull('closed_at')->count());

        // Backdated history, notes on every deal, and descriptions written in plain English.
        $this->assertTrue(Deal::min('created_at') < now()->subDays(90));
        $this->assertSame(22, DealActivity::where('type', 'note')->distinct()->count('deal_id'));
        $this->assertStringContainsString('pool', Property::where('title', 'like', '%Epping%')->where('type', 'house')->value('description'));
    }
}
