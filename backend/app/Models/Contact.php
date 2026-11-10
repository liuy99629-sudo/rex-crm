<?php

namespace App\Models;

use App\Enums\ContactType;
use App\Services\PipelineService;
use Database\Factories\ContactFactory;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Contact extends Model
{
    /** @use HasFactory<ContactFactory> */
    use HasFactory;

    protected $fillable = [
        'user_id', 'name', 'email', 'phone', 'type', 'source',
        'budget_min', 'budget_max', 'notes',
    ];

    protected function casts(): array
    {
        return [
            'type' => ContactType::class,
            'budget_min' => 'integer',
            'budget_max' => 'integer',
        ];
    }

    protected static function booted(): void
    {
        // The dashboard counts contacts, and deleting one cascades to its deals in the database
        // (no Deal events fire): drop the cached pipeline board / dashboard numbers.
        $flush = fn () => app(PipelineService::class)->flush();

        static::saved($flush);
        static::deleted($flush);
    }

    public function agent(): BelongsTo
    {
        return $this->belongsTo(User::class, 'user_id');
    }

    public function deals(): HasMany
    {
        return $this->hasMany(Deal::class);
    }

    public function ownedProperties(): HasMany
    {
        return $this->hasMany(Property::class, 'owner_id');
    }

    /** Case-insensitive search on name / email / phone (portable across PostgreSQL and SQLite). */
    public function scopeSearch(Builder $query, ?string $term): Builder
    {
        if ($term === null || trim($term) === '') {
            return $query;
        }

        $like = '%'.mb_strtolower(trim($term)).'%';

        return $query->where(function (Builder $w) use ($like) {
            $w->whereRaw('LOWER(name) LIKE ?', [$like])
                ->orWhereRaw('LOWER(email) LIKE ?', [$like])
                ->orWhereRaw('LOWER(phone) LIKE ?', [$like]);
        });
    }
}
