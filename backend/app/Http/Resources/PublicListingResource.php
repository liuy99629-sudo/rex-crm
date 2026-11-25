<?php

namespace App\Http\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/**
 * A listing as the public website may show it: no owner (vendor) details, no internal ids
 * beyond the listing itself, and only the listing agent's name.
 *
 * @mixin \App\Models\Property
 */
class PublicListingResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'title' => $this->title,
            'address_line' => $this->address_line,
            'suburb' => $this->suburb,
            'state' => $this->state,
            'postcode' => $this->postcode,
            'type' => $this->type->value,
            'status' => $this->status->value,
            'price' => $this->price,
            'bedrooms' => $this->bedrooms,
            'bathrooms' => $this->bathrooms,
            'parking' => $this->parking,
            'land_size_sqm' => $this->land_size_sqm,
            'description' => $this->description,
            'listed_at' => $this->listed_at?->toDateString(),
            'agent_name' => $this->whenLoaded('agent', fn () => $this->agent?->name),
        ];
    }
}
