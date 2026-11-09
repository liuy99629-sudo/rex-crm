<?php

namespace App\Http\Controllers\Api;

use App\Enums\ContactType;
use App\Http\Controllers\Controller;
use App\Http\Resources\ContactResource;
use App\Models\Contact;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Validation\Rule;

class ContactController extends Controller
{
    public function index(Request $request): AnonymousResourceCollection
    {
        $contacts = Contact::query()
            ->with('agent:id,name')
            ->withCount('deals')
            ->search($request->query('q'))
            ->when($request->query('type'), fn ($q, $type) => $q->where('type', $type))
            ->orderBy('name')
            ->paginate(min(max($request->integer('per_page', 20), 1), 100));

        return ContactResource::collection($contacts);
    }

    public function store(Request $request): JsonResponse
    {
        $contact = Contact::create($this->validated($request) + ['user_id' => $request->user()->id]);

        return (new ContactResource($contact->load('agent:id,name')))
            ->response()
            ->setStatusCode(201);
    }

    public function show(Contact $contact): ContactResource
    {
        return new ContactResource($contact->load('agent:id,name')->loadCount('deals'));
    }

    public function update(Request $request, Contact $contact): ContactResource
    {
        $contact->update($this->validated($request));

        return new ContactResource($contact->load('agent:id,name')->loadCount('deals'));
    }

    public function destroy(Contact $contact): JsonResponse
    {
        $contact->delete();

        return response()->json(null, 204);
    }

    /** @return array<string, mixed> */
    private function validated(Request $request): array
    {
        return $request->validate([
            'name' => ['required', 'string', 'max:255'],
            'email' => ['nullable', 'email', 'max:255'],
            'phone' => ['nullable', 'string', 'max:50'],
            'type' => ['required', Rule::enum(ContactType::class)],
            'source' => ['nullable', 'string', 'max:100'],
            'budget_min' => ['nullable', 'integer', 'min:0'],
            'budget_max' => ['nullable', 'integer', 'min:0', Rule::when($request->filled('budget_min'), ['gte:budget_min'])],
            'notes' => ['nullable', 'string', 'max:5000'],
        ]);
    }
}
