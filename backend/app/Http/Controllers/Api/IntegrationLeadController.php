<?php

namespace App\Http\Controllers\Api;

use App\Enums\PropertyStatus;
use App\Http\Controllers\Controller;
use App\Models\Property;
use App\Services\LeadIntake;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

/**
 * Leads from machine integrations (the AWS email pipeline: portal enquiry emails parsed by Claude).
 * Needs a token with the `leads:write` ability (php artisan rex:integration-token).
 * The listing is found from a free-text hint (address or title) taken from the email.
 */
class IntegrationLeadController extends Controller
{
    public function store(Request $request, LeadIntake $intake): JsonResponse
    {
        $data = $request->validate([
            'source' => ['required', 'string', 'max:50'],
            'external_id' => ['required', 'string', 'max:255'],
            'name' => ['required', 'string', 'max:255'],
            'email' => ['required', 'email', 'max:255'],
            'phone' => ['nullable', 'string', 'max:50'],
            'message' => ['required', 'string', 'max:5000'],
            'listing_hint' => ['nullable', 'string', 'max:255'],
            'budget_min' => ['nullable', 'integer', 'min:0'],
            'budget_max' => ['nullable', 'integer', 'min:0'],
        ]);

        $listing = $this->findListing($data['listing_hint'] ?? null);
        $deal = $intake->receive($data, $listing, $data['source']);

        return response()->json([
            'deal_id' => $deal->id,
            'contact_id' => $deal->contact_id,
            'listing_id' => $listing?->id,
            'reference' => sprintf('ENQ-%05d', $deal->id),
        ], 201);
    }

    /** Best listing for a hint like "14 Kent Street, Epping" or "Family home with pool in Epping". */
    private function findListing(?string $hint): ?Property
    {
        if ($hint === null || trim($hint) === '') {
            return null;
        }
        $open = fn () => Property::query()->whereNotIn('status', [PropertyStatus::Sold->value, PropertyStatus::Withdrawn->value]);

        // 1. The street address (text before the first comma) appears in the listing's address.
        $street = mb_strtolower(trim(explode(',', $hint)[0]));
        if ($street !== '') {
            $byAddress = $open()->whereRaw('LOWER(address_line) LIKE ?', ['%'.$street.'%'])->first();
            if ($byAddress) {
                return $byAddress;
            }
        }

        // 2. Exact title, then the whole hint matching title/address/suburb.
        return $open()->whereRaw('LOWER(title) = ?', [mb_strtolower(trim($hint))])->first()
            ?? $open()->search($hint)->orderBy('id')->first();
    }
}
