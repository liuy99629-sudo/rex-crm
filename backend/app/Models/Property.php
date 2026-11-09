<?php

namespace App\Models;

use App\Enums\PropertyStatus;
use App\Enums\PropertyType;
use Database\Factories\PropertyFactory;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Property extends Model
{
    /** @use HasFactory<PropertyFactory> */
    use HasFactory;

    protected $fillable = [
        'user_id', 'owner_id', 'title', 'address_line', 'suburb', 'state', 'postcode',
        'type', 'status', 'price', 'bedrooms', 'bathrooms', 'parking',
        'land_size_sqm', 'description', 'listed_at',
    ];

    protected function casts(): array
    {
        return [
            'type' => PropertyType::class,
            'status' => PropertyStatus::class,
            'price' => 'integer',
            'listed_at' => 'date',
        ];
    }

    public function agent(): BelongsTo
    {
        return $this->belongsTo(User::class, 'user_id');
    }

    public function owner(): BelongsTo
    {
        return $this->belongsTo(Contact::class, 'owner_id');
    }

    public function deals(): HasMany
    {
        return $this->hasMany(Deal::class);
    }

    public function scopeSearch(Builder $query, ?string $term): Builder
    {
        if ($term === null || trim($term) === '') {
            return $query;
        }

        $like = '%'.mb_strtolower(trim($term)).'%';

        return $query->where(function (Builder $w) use ($like) {
            $w->whereRaw('LOWER(title) LIKE ?', [$like])
                ->orWhereRaw('LOWER(address_line) LIKE ?', [$like])
                ->orWhereRaw('LOWER(suburb) LIKE ?', [$like]);
        });
    }
}
