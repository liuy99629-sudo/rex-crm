<?php

namespace App\Http\Controllers\Api;

use App\Enums\PropertyStatus;
use App\Enums\PropertyType;
use App\Http\Controllers\Controller;
use App\Http\Resources\PropertyResource;
use App\Models\Property;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Validation\Rule;

class PropertyController extends Controller
{
    public function index(Request $request): AnonymousResourceCollection
    {
        $properties = Property::query()
            ->with(['owner:id,name', 'agent:id,name'])
            ->search($request->query('q'))
            ->when($request->query('status'), fn ($q, $v) => $q->where('status', $v))
            ->when($request->query('type'), fn ($q, $v) => $q->where('type', $v))
            ->when($request->query('min_price'), fn ($q, $v) => $q->where('price', '>=', (int) $v))
            ->when($request->query('max_price'), fn ($q, $v) => $q->where('price', '<=', (int) $v))
            ->latest('id')
            ->paginate(min(max($request->integer('per_page', 20), 1), 100));

        return PropertyResource::collection($properties);
    }

    public function store(Request $request): JsonResponse
    {
        $property = Property::create($this->validated($request) + ['user_id' => $request->user()->id]);

        return (new PropertyResource($property->load(['owner:id,name', 'agent:id,name'])))
            ->response()
            ->setStatusCode(201);
    }

    public function show(Property $property): PropertyResource
    {
        return new PropertyResource($property->load(['owner:id,name', 'agent:id,name']));
    }

    public function update(Request $request, Property $property): PropertyResource
    {
        $property->update($this->validated($request));

        return new PropertyResource($property->load(['owner:id,name', 'agent:id,name']));
    }

    public function destroy(Property $property): JsonResponse
    {
        $property->delete();

        return response()->json(null, 204);
    }

    /** @return array<string, mixed> */
    private function validated(Request $request): array
    {
        return $request->validate([
            'title' => ['required', 'string', 'max:255'],
            'address_line' => ['required', 'string', 'max:255'],
            'suburb' => ['required', 'string', 'max:100'],
            'state' => ['required', Rule::in(['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT'])],
            'postcode' => ['required', 'digits:4'],
            'type' => ['required', Rule::enum(PropertyType::class)],
            'status' => ['required', Rule::enum(PropertyStatus::class)],
            'price' => ['nullable', 'integer', 'min:0'],
            'bedrooms' => ['nullable', 'integer', 'min:0', 'max:50'],
            'bathrooms' => ['nullable', 'integer', 'min:0', 'max:50'],
            'parking' => ['nullable', 'integer', 'min:0', 'max:50'],
            'land_size_sqm' => ['nullable', 'integer', 'min:0'],
            'description' => ['nullable', 'string', 'max:10000'],
            'listed_at' => ['nullable', 'date'],
            'owner_id' => ['nullable', 'integer', 'exists:contacts,id'],
        ]);
    }
}
