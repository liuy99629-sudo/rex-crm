<?php

namespace App\Enums;

enum PropertyStatus: string
{
    case Draft = 'draft';
    case Active = 'active';
    case UnderOffer = 'under_offer';
    case Sold = 'sold';
    case Withdrawn = 'withdrawn';

    /** @return list<string> */
    public static function values(): array
    {
        return array_column(self::cases(), 'value');
    }
}
