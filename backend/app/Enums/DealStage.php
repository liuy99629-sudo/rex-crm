<?php

namespace App\Enums;

enum DealStage: string
{
    case Lead = 'lead';
    case Contacted = 'contacted';
    case Inspection = 'inspection';
    case Offer = 'offer';
    case Negotiation = 'negotiation';
    case Won = 'won';
    case Lost = 'lost';

    public function label(): string
    {
        return match ($this) {
            self::Lead => 'Lead',
            self::Contacted => 'Contacted',
            self::Inspection => 'Inspection',
            self::Offer => 'Offer',
            self::Negotiation => 'Negotiation',
            self::Won => 'Won',
            self::Lost => 'Lost',
        };
    }

    public function isClosed(): bool
    {
        return in_array($this, [self::Won, self::Lost], true);
    }

    /** @return list<string> */
    public static function values(): array
    {
        return array_column(self::cases(), 'value');
    }

    /** @return list<string> */
    public static function openValues(): array
    {
        return array_values(array_map(
            fn (self $s) => $s->value,
            array_filter(self::cases(), fn (self $s) => ! $s->isClosed())
        ));
    }
}
