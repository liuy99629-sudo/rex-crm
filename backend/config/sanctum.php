<?php

use Laravel\Sanctum\Sanctum;

return [
    // Token (bearer) authentication only: no stateful SPA domains.
    'stateful' => [],

    'guard' => [],

    'expiration' => env('SANCTUM_TOKEN_EXPIRATION_MINUTES', 60 * 24 * 7),

    'token_prefix' => env('SANCTUM_TOKEN_PREFIX', ''),

    'middleware' => [
        'authenticate_session' => Laravel\Sanctum\Http\Middleware\AuthenticateSession::class,
        'encrypt_cookies' => Illuminate\Cookie\Middleware\EncryptCookies::class,
        'validate_csrf_token' => Illuminate\Foundation\Http\Middleware\ValidateCsrfToken::class,
    ],
];
