<?php

namespace App\Http\Controllers\Api;

use App\Enums\PropertyStatus;
use App\Enums\PropertyType;
use App\Http\Controllers\Controller;
use App\Http\Resources\PublicListingResource;
use App\Models\Property;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Validation\Rule;

/**
 * Read-only listings for the public website (no login). Only listings on the market are
 * visible: drafts, sold and withdrawn properties are not.
 */
class PublicListingController extends Controller
{
    public const VISIBLE = [PropertyStatus::Active, PropertyStatus::UnderOffer];

    public function index(Request $request): AnonymousResourceCollection
    {
        $filters = $request->validate([
            'q' => ['nullable', 'string', 'max:100'],
            'suburb' => ['nullable', 'string', 'max:100'],
            'type' => ['nullable', Rule::enum(PropertyType::class)],
            'min_price' => ['nullable', 'integer', 'min:0'],
            'max_price' => ['nullable', 'integer', 'min:0'],
            'min_bedrooms' => ['nullable', 'integer', 'min:0', 'max:20'],
            'per_page' => ['nullable', 'integer', 'min:1', 'max:50'],
        ]);

        $listings = self::visible()
            ->with('agent:id,name')
            ->search($filters['q'] ?? null)
            ->when($filters['suburb'] ?? null, fn (Builder $q, $v) => $q->whereRaw('LOWER(suburb) = ?', [mb_strtolower($v)]))
            ->when($filters['type'] ?? null, fn (Builder $q, $v) => $q->where('type', $v))
            ->when(isset($filters['min_price']), fn (Builder $q) => $q->where('price', '>=', $filters['min_price']))
            ->when(isset($filters['max_price']), fn (Builder $q) => $q->where('price', '<=', $filters['max_price']))
            ->when(isset($filters['min_bedrooms']), fn (Builder $q) => $q->where('bedrooms', '>=', $filters['min_bedrooms']))
            ->orderByDesc('listed_at')
            ->orderByDesc('id')
            ->paginate($filters['per_page'] ?? 12);

        return PublicListingResource::collection($listings);
    }

    public function show(int $id): PublicListingResource
    {
        return new PublicListingResource(self::visible()->with('agent:id,name')->findOrFail($id));
    }

    /** @return Builder<Property> */
    public static function visible(): Builder
    {
        return Property::query()->whereIn('status', array_map(fn ($s) => $s->value, self::VISIBLE));
    }
}
