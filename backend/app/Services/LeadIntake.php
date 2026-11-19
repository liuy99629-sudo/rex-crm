<?php

namespace App\Services;

use App\Enums\ContactType;
use App\Enums\DealStage;
use App\Models\Contact;
use App\Models\Deal;
use App\Models\Property;
use Illuminate\Support\Facades\DB;

/**
 * Turns an incoming enquiry (website form, portal email, ...) into CRM work:
 * the contact (matched by email, or created), a Lead deal assigned to the listing's agent,
 * and the message as a note. A repeat enquiry on the same listing adds a note to the open deal
 * instead of creating a duplicate. Everything goes through Eloquent, so the pipeline cache is flushed.
 */
class LeadIntake
{
    /**
     * @param  array{name: string, email: string, phone?: ?string, message: string, budget_min?: ?int, budget_max?: ?int}  $lead
     */
    public function receive(array $lead, ?Property $listing, string $source): Deal
    {
        return DB::transaction(function () use ($lead, $listing, $source) {
            $contact = Contact::query()->whereRaw('LOWER(email) = ?', [mb_strtolower($lead['email'])])->first();

            if ($contact === null) {
                $contact = Contact::create([
                    'name' => $lead['name'],
                    'email' => $lead['email'],
                    'phone' => $lead['phone'] ?? null,
                    'type' => ContactType::Buyer,
                    'source' => $source,
                    'user_id' => $listing?->user_id,
                    'budget_min' => $lead['budget_min'] ?? null,
                    'budget_max' => $lead['budget_max'] ?? null,
                ]);
            } else {
                // Fill gaps only; never overwrite what an agent has recorded.
                $contact->fill(array_filter([
                    'phone' => $contact->phone ? null : ($lead['phone'] ?? null),
                    'budget_min' => $contact->budget_min !== null ? null : ($lead['budget_min'] ?? null),
                    'budget_max' => $contact->budget_max !== null ? null : ($lead['budget_max'] ?? null),
                ], fn ($v) => $v !== null))->save();
            }

            $deal = Deal::query()
                ->where('contact_id', $contact->id)
                ->where('property_id', $listing?->id)
                ->whereIn('stage', DealStage::openValues())
                ->first()
                ?? Deal::create([
                    'title' => "{$source} enquiry - {$contact->name}",
                    'contact_id' => $contact->id,
                    'property_id' => $listing?->id,
                    'user_id' => $listing?->user_id ?? $contact->user_id,
                    'stage' => DealStage::Lead,
                    'value' => $listing?->price ?? $lead['budget_max'] ?? 0,
                ]);

            $deal->activities()->create([
                'type' => 'note',
                'body' => "{$source} enquiry: {$lead['message']}"
                    .(($lead['phone'] ?? null) ? "\nPhone: {$lead['phone']}" : ''),
            ]);

            return $deal;
        });
    }
}
