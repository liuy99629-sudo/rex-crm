<?php

namespace App\Http\Controllers\Api;

use App\Enums\ContactType;
use App\Enums\DealStage;
use App\Http\Controllers\Controller;
use App\Models\Contact;
use App\Models\Deal;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/**
 * "Enquire about this property" from the public website. Turns the enquiry into CRM work:
 * the contact (matched by email, or created), a Lead deal on the listing assigned to its agent,
 * and the message as a note. A repeat enquiry on the same listing adds a note to the open deal
 * instead of creating a duplicate. Everything goes through Eloquent, so the pipeline cache is flushed.
 */
class PublicEnquiryController extends Controller
{
    public function store(Request $request): JsonResponse
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

        $deal = DB::transaction(function () use ($data, $listing) {
            $contact = Contact::query()->whereRaw('LOWER(email) = ?', [mb_strtolower($data['email'])])->first()
                ?? Contact::create([
                    'name' => $data['name'],
                    'email' => $data['email'],
                    'phone' => $data['phone'] ?? null,
                    'type' => ContactType::Buyer,
                    'source' => 'Website',
                    'user_id' => $listing->user_id,
                ]);

            $deal = Deal::query()
                ->where('contact_id', $contact->id)
                ->where('property_id', $listing->id)
                ->whereIn('stage', DealStage::openValues())
                ->first()
                ?? Deal::create([
                    'title' => "Website enquiry - {$contact->name}",
                    'contact_id' => $contact->id,
                    'property_id' => $listing->id,
                    'user_id' => $listing->user_id,
                    'stage' => DealStage::Lead,
                    'value' => $listing->price ?? 0,
                ]);

            $deal->activities()->create([
                'type' => 'note',
                'body' => "Website enquiry: {$data['message']}"
                    .($data['phone'] ?? null ? "\nPhone: {$data['phone']}" : ''),
            ]);

            return $deal;
        });

        return response()->json([
            'reference' => sprintf('ENQ-%05d', $deal->id),
            'message' => 'Thanks! The listing agent will be in touch shortly.',
        ], 201);
    }
}
