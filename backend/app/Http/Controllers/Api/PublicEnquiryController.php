<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Services\LeadIntake;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

/** "Enquire about this property" from the public website (see LeadIntake for what it creates). */
class PublicEnquiryController extends Controller
{
    public function store(Request $request, LeadIntake $intake): JsonResponse
    {
        $data = $request->validate([
            'listing_id' => ['required', 'integer'],
            'name' => ['required', 'string', 'max:255'],
            'email' => ['required', 'email', 'max:255'],
            'phone' => ['nullable', 'string', 'max:50'],
            'message' => ['required', 'string', 'max:2000'],
            // Honeypot: hidden on the form, so only bots fill it in.
            'website' => ['nullable', 'string', 'max:0'],
        ]);

        $listing = PublicListingController::visible()->findOrFail($data['listing_id']);
        $deal = $intake->receive($data, $listing, 'Website');

        return response()->json([
            'reference' => sprintf('ENQ-%05d', $deal->id),
            'message' => 'Thanks! The listing agent will be in touch shortly.',
        ], 201);
    }
}
