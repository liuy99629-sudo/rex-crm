# syntax=docker/dockerfile:1

# ---- Stage 1: PHP dependencies ------------------------------------------------
FROM composer:2 AS vendor
WORKDIR /app
COPY composer.json composer.lock* ./
RUN composer install --no-dev --no-scripts --no-autoloader --prefer-dist --no-interaction
COPY . .
RUN composer dump-autoload --optimize --no-dev --no-scripts

# ---- Stage 2: runtime (nginx + php-fpm, runs as non-root on :8080) -----------
FROM serversideup/php:8.3-fpm-nginx AS app
WORKDIR /var/www/html

# The same image runs the API (default command) and the queue worker (command override).
COPY --chown=www-data:www-data --from=vendor /app /var/www/html

# Register package service providers (Sanctum, Tinker...) now that vendor/ is in place.
RUN php artisan package:discover --ansi

ENV PHP_OPCACHE_ENABLE=1 \
    LOG_CHANNEL=stderr \
    SSL_MODE=off

EXPOSE 8080

# ---- Optional: test runner (docker compose --profile test run --rm test) ----------
FROM serversideup/php:8.3-cli AS test
USER root
RUN install-php-extensions pdo_sqlite
WORKDIR /var/www/html
COPY --chown=www-data:www-data . .
USER www-data
RUN composer install --no-interaction --prefer-dist --no-progress && cp .env.example .env && php artisan key:generate
CMD ["php", "artisan", "test"]
