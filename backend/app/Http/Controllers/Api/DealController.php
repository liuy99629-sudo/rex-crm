<?php

namespace App\Http\Controllers\Api;

use App\Enums\DealStage;
use App\Http\Controllers\Controller;
use App\Http\Resources\DealActivityResource;
use App\Http\Resources\DealResource;
use App\Jobs\RecordDealStageChange;
use App\Models\Deal;
use App\Models\DealActivity;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Validation\Rule;

class DealController extends Controller
{
    private const RELATIONS = ['contact:id,name', 'property:id,title,suburb', 'agent:id,name'];

    public function index(Request $request): AnonymousResourceCollection
    {
        $deals = Deal::query()
            ->with(self::RELATIONS)
            ->when($request->query('stage'), fn ($q, $v) => $q->where('stage', $v))
            ->when($request->query('contact_id'), fn ($q, $v) => $q->where('contact_id', $v))
            ->latest('updated_at')
            ->paginate(min(max($request->integer('per_page', 20), 1), 100));

        return DealResource::collection($deals);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'title' => ['required', 'string', 'max:255'],
            'contact_id' => ['required', 'integer', 'exists:contacts,id'],
            'property_id' => ['nullable', 'integer', 'exists:properties,id'],
            'stage' => ['nullable', Rule::enum(DealStage::class)],
            'value' => ['nullable', 'integer', 'min:0'],
            'expected_close_date' => ['nullable', 'date'],
            'notes' => ['nullable', 'string', 'max:5000'],
        ]);

        $data['stage'] ??= DealStage::Lead->value;

        $deal = Deal::create($data + ['user_id' => $request->user()->id]);

        return (new DealResource($deal->load(self::RELATIONS)))
            ->response()
            ->setStatusCode(201);
    }

    public function show(Deal $deal): DealResource
    {
        return new DealResource($deal->load([...self::RELATIONS, 'activities.user:id,name']));
    }

    public function update(Request $request, Deal $deal): DealResource
    {
        $data = $request->validate([
            'title' => ['sometimes', 'required', 'string', 'max:255'],
            'contact_id' => ['sometimes', 'required', 'integer', 'exists:contacts,id'],
            'property_id' => ['nullable', 'integer', 'exists:properties,id'],
            'value' => ['nullable', 'integer', 'min:0'],
            'expected_close_date' => ['nullable', 'date'],
            'notes' => ['nullable', 'string', 'max:5000'],
        ]);

        $deal->update($data);

        return new DealResource($deal->load([...self::RELATIONS, 'activities.user:id,name']));
    }

    public function destroy(Deal $deal): JsonResponse
    {
        $deal->delete();

        return response()->json(null, 204);
    }

    /**
     * Move a deal to another pipeline stage.
     * The stage is saved immediately; the activity log entry and side effects are queued for the worker.
     */
    public function updateStage(Request $request, Deal $deal): DealResource
    {
        $data = $request->validate([
            'stage' => ['required', Rule::enum(DealStage::class)],
        ]);

        $from = $deal->stage;
        $to = DealStage::from($data['stage']);

        if ($from !== $to) {
            $deal->update([
                'stage' => $to,
                'closed_at' => $to->isClosed() ? now() : null,
            ]);

            RecordDealStageChange::dispatch($deal->id, $from->value, $to->value, $request->user()->id);
        }

        return new DealResource($deal->load(self::RELATIONS));
    }

    public function addNote(Request $request, Deal $deal): JsonResponse
    {
        $data = $request->validate(['body' => ['required', 'string', 'max:5000']]);

        $activity = $deal->activities()->create([
            'user_id' => $request->user()->id,
            'type' => 'note',
            'body' => $data['body'],
        ]);

        return (new DealActivityResource($activity->load('user:id,name')))
            ->response()
            ->setStatusCode(201);
    }

    /** Delete a note. Stage-change entries are the deal's history and stay. */
    public function deleteNote(Deal $deal, DealActivity $activity): JsonResponse
    {
        abort_unless($activity->type === 'note', 403, 'Only notes can be deleted.');

        $activity->delete();

        return response()->json(null, 204);
    }
}
