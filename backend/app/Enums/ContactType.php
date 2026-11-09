<?php

namespace App\Enums;

enum ContactType: string
{
    case Buyer = 'buyer';
    case Seller = 'seller';
    case Investor = 'investor';
    case Tenant = 'tenant';
    case Landlord = 'landlord';

    /** @return list<string> */
    public static function values(): array
    {
        return array_column(self::cases(), 'value');
    }
}
