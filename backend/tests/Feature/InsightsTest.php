<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Laravel\Sanctum\Sanctum;
use Tests\TestCase;

class InsightsTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        Sanctum::actingAs(User::factory()->create());
    }

    public function test_reports_unavailable_before_the_first_analytics_run(): void
    {
        $this->getJson('/api/insights')->assertOk()->assertExactJson(['available' => false]);
    }

    public function test_returns_the_marts_written_by_the_spark_job(): void
    {
        // The Spark job creates these tables; mimic a run.
        Schema::create('analytics_run_info', function (Blueprint $t) {
            $t->timestamp('finished_at');
            $t->double('seconds');
            $t->text('row_counts');
        });
        Schema::create('analytics_suburb_market', function (Blueprint $t) {
            $t->string('suburb');
            $t->string('property_type');
            $t->bigInteger('listings');
            $t->bigInteger('on_market');
        });
        Schema::create('analytics_lead_funnel', function (Blueprint $t) {
            $t->string('lead_source');
            $t->bigInteger('deals');
            $t->double('win_rate')->nullable();
        });
        DB::table('analytics_run_info')->insert(['finished_at' => '2026-11-19 03:00:00', 'seconds' => 12.5, 'row_counts' => '{}']);
        DB::table('analytics_suburb_market')->insert([
            ['suburb' => 'Bondi', 'property_type' => 'apartment', 'listings' => 2, 'on_market' => 1],
            ['suburb' => 'Epping', 'property_type' => 'house', 'listings' => 3, 'on_market' => 2],
        ]);
        DB::table('analytics_lead_funnel')->insert(['lead_source' => 'Domain', 'deals' => 3, 'win_rate' => 0.667]);

        $this->getJson('/api/insights')
            ->assertOk()
            ->assertJsonPath('available', true)
            ->assertJsonPath('refreshed_at', '2026-11-19T03:00:00+00:00')
            ->assertJsonPath('suburb_market.0.suburb', 'Epping') // most on the market first
            ->assertJsonPath('lead_funnel.0.lead_source', 'Domain')
            ->assertJsonPath('agent_performance', []) // a mart not written yet is just empty
            ->assertJsonPath('stage_velocity', []);
    }

    public function test_requires_login(): void
    {
        $this->app['auth']->forgetGuards();
        $this->withHeaders(['Authorization' => ''])->getJson('/api/insights')->assertUnauthorized();
    }
}
