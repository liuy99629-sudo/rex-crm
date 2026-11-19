<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * The CRM's own routes are for people. Integration tokens (created with only integration
 * abilities, e.g. leads:write) must not read or change anything else. Login tokens carry '*'.
 */
class RejectLimitedTokens
{
    /** Abilities that only machine integrations get. */
    public const INTEGRATION_ABILITIES = ['leads:write'];

    public function handle(Request $request, Closure $next): Response
    {
        $token = $request->user()?->currentAccessToken();

        if ($token && method_exists($token, 'can') && ! $token->can('*')) {
            foreach (self::INTEGRATION_ABILITIES as $ability) {
                if ($token->can($ability)) {
                    abort(403, 'This token is limited to integrations.');
                }
            }
        }

        return $next($request);
    }
}
