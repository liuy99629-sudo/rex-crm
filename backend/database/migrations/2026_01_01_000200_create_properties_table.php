<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('properties', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->nullable()->constrained()->nullOnDelete(); // listing agent
            $table->foreignId('owner_id')->nullable()->constrained('contacts')->nullOnDelete(); // vendor
            $table->string('title');
            $table->string('address_line');
            $table->string('suburb');
            $table->string('state', 3);
            $table->string('postcode', 4);
            $table->string('type')->default('house');
            $table->string('status')->default('draft');
            $table->unsignedBigInteger('price')->nullable();
            $table->unsignedSmallInteger('bedrooms')->nullable();
            $table->unsignedSmallInteger('bathrooms')->nullable();
            $table->unsignedSmallInteger('parking')->nullable();
            $table->unsignedInteger('land_size_sqm')->nullable();
            $table->text('description')->nullable();
            $table->date('listed_at')->nullable();
            $table->timestamps();

            $table->index('status');
            $table->index('type');
            $table->index('suburb');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('properties');
    }
};
