<?php

namespace App\Console\Commands;

use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Support\Str;

/**
 * Creates a limited API token for a machine integration, e.g. the AWS lead pipeline:
 *   php artisan rex:integration-token lead-pipeline
 * The token can only call /api/integrations/leads. Store it as a secret; it is shown once.
 */
class CreateIntegrationToken extends Command
{
    protected $signature = 'rex:integration-token {name : e.g. lead-pipeline}';

    protected $description = 'Create an API token limited to posting leads (leads:write)';

    public function handle(): int
    {
        $name = $this->argument('name');
        $user = User::firstOrCreate(
            ['email' => "integration+{$name}@rexcrm.invalid"],
            ['name' => "Integration: {$name}", 'role' => 'agent', 'password' => Str::random(64)],
        );

        $token = $user->createToken($name, ['leads:write'])->plainTextToken;

        $this->info("Token for {$name} (shown once; store it as a secret):");
        $this->line($token);

        return self::SUCCESS;
    }
}
