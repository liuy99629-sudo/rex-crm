<?php

namespace App\Models;

use App\Enums\DealStage;
use App\Services\PipelineService;
use Database\Factories\DealFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Deal extends Model
{
    /** @use HasFactory<DealFactory> */
    use HasFactory;

    protected $fillable = [
        'title', 'contact_id', 'property_id', 'user_id', 'stage',
        'value', 'expected_close_date', 'closed_at', 'notes',
    ];

    /**
     * Mirrors the column default so a freshly created deal has its stage in memory
     * (Eloquent does not read database defaults back after insert).
     */
    protected $attributes = [
        'stage' => 'lead',
    ];

    protected function casts(): array
    {
        return [
            'stage' => DealStage::class,
            'value' => 'integer',
            'expected_close_date' => 'date',
            'closed_at' => 'datetime',
        ];
    }

    protected static function booted(): void
    {
        // Any change to a deal invalidates the cached pipeline board / dashboard numbers.
        $flush = fn () => app(PipelineService::class)->flush();

        static::saved($flush);
        static::deleted($flush);
    }

    public function contact(): BelongsTo
    {
        return $this->belongsTo(Contact::class);
    }

    public function property(): BelongsTo
    {
        return $this->belongsTo(Property::class);
    }

    public function agent(): BelongsTo
    {
        return $this->belongsTo(User::class, 'user_id');
    }

    public function activities(): HasMany
    {
        return $this->hasMany(DealActivity::class)->latest();
    }
}
