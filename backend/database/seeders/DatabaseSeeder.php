<?php

namespace Database\Seeders;

use App\Enums\DealStage;
use App\Models\Contact;
use App\Models\Deal;
use App\Models\DealActivity;
use App\Models\Property;
use App\Models\User;
use Illuminate\Database\Seeder;

class DatabaseSeeder extends Seeder
{
    /**
     * Demo data. Login: admin@rexcrm.test / password
     *
     * Hand-written so the AI features have something real to work with: listing descriptions and
     * client notes describe what buyers want (pools, schools, stations...), and closed deals give
     * the win-probability model genuine outcomes. Fictional people, example.com emails.
     */
    public function run(): void
    {
        // Safe to re-run (README says to seed after `docker compose up`, and the pgdata volume persists).
        if (User::where('email', 'admin@rexcrm.test')->exists()) {
            $this->command?->info('Demo data already present, skipping.');

            return;
        }

        $admin = User::factory()->admin()->create(['name' => 'Demo Admin', 'email' => 'admin@rexcrm.test']);
        $agent = User::factory()->create(['name' => 'Demo Agent', 'email' => 'agent@rexcrm.test']);
        $agentFor = fn (int $i) => $i % 2 ? $admin->id : $agent->id;

        $contacts = [];
        foreach (self::CONTACTS as $i => [$key, $name, $type, $min, $max, $source, $notes]) {
            $contacts[$key] = Contact::create([
                'user_id' => $agentFor($i),
                'name' => $name,
                'email' => strtolower(str_replace([' ', "'"], ['.', ''], $name)).'@example.com',
                'phone' => sprintf('04%02d %03d %03d', 10 + $i * 5, 100 + $i * 37, 200 + $i * 53),
                'type' => $type,
                'source' => $source,
                'budget_min' => $min,
                'budget_max' => $max,
                'notes' => $notes,
            ]);
        }

        $properties = [];
        foreach (self::PROPERTIES as $i => $p) {
            [$key, $title, $address, $suburb, $postcode, $type, $status, $price, $bed, $bath, $car, $land, $owner, $description] = $p;
            $properties[$key] = Property::create([
                'user_id' => $agentFor($i),
                'owner_id' => $owner ? $contacts[$owner]->id : null,
                'title' => $title,
                'address_line' => $address,
                'suburb' => $suburb,
                'state' => 'NSW',
                'postcode' => $postcode,
                'type' => $type,
                'status' => $status,
                'price' => $price,
                'bedrooms' => $bed,
                'bathrooms' => $bath,
                'parking' => $car,
                'land_size_sqm' => $land,
                'description' => $description,
                'listed_at' => now()->subDays(20 + $i * 6)->toDateString(),
            ]);
        }

        foreach (self::DEALS as $i => [$title, $contact, $property, $stage, $value, $ageDays, $closeInDays, $closedDaysAgo, $notes]) {
            $created = now()->subDays($ageDays);
            $stage = DealStage::from($stage);
            $deal = new Deal([
                'title' => $title,
                'contact_id' => $contacts[$contact]->id,
                'property_id' => $property ? $properties[$property]->id : null,
                'user_id' => $agentFor($i),
                'stage' => $stage,
                'value' => $value,
                'expected_close_date' => $closeInDays === null ? null : now()->addDays($closeInDays)->toDateString(),
                'closed_at' => $stage->isClosed() ? now()->subDays($closedDaysAgo) : null,
            ]);
            $deal->created_at = $created;
            $deal->updated_at = $stage->isClosed() ? now()->subDays($closedDaysAgo) : $created->copy()->addDays(count($notes) * 3);
            $deal->save();

            foreach ($notes as $n => $body) {
                $activity = new DealActivity(['user_id' => $deal->user_id, 'type' => 'note', 'body' => $body]);
                $activity->deal_id = $deal->id;
                $activity->created_at = $activity->updated_at = $created->copy()->addDays(1 + $n * 4)->min(now());
                $activity->save();
            }
        }
    }

    /** [key, name, type, budget_min, budget_max, source, notes] */
    private const CONTACTS = [
        ['priya', 'Priya Sharma', 'buyer', 1_600_000, 1_900_000, 'Domain', 'Family of five. Needs 4+ bedrooms, a pool for the kids and a good school catchment around Epping or Carlingford. Finance pre-approved.'],
        ['daniel', 'Daniel Wong', 'buyer', 1_000_000, 1_200_000, 'realestate.com.au', 'First home buyers, a couple with a dog. Want a 2-bedroom apartment near a North Shore train station; the building must be pet-friendly.'],
        ['olivia', 'Olivia Bennett', 'investor', 550_000, 700_000, 'Referral', 'Building a rental portfolio. Wants low strata levies and strong rental demand near a university or hospital. Yield matters more than views.'],
        ['marco', 'Marco Rossi', 'buyer', 1_300_000, 1_500_000, 'Open home', 'Downsizing from a large house. Prefers a low-maintenance townhouse with a courtyard, close to shops and the station in the inner west.'],
        ['james', "James O'Connor", 'investor', 900_000, 1_300_000, 'Referral', 'Small developer. Looking for sites with DA approval or duplex potential in western or southern Sydney.'],
        ['aisha', 'Aisha Rahman', 'buyer', 1_600_000, 1_800_000, 'Domain', 'Works from home and needs a dedicated study. Wants a 3-bedroom townhouse in Chatswood or Willoughby near schools. Has a cat.'],
        ['tom', 'Tom Nguyen', 'buyer', 1_000_000, 1_150_000, 'Walk-in', 'Young family upsizing. Needs 3 bedrooms near a station; an apartment is fine if it has a study.'],
        ['sophie', 'Sophie Martin', 'buyer', 1_600_000, 1_900_000, 'realestate.com.au', 'Relocating from Melbourne. Wants to walk to the beach; 2 bedrooms with lots of natural light.'],
        ['rajesh', 'Rajesh Patel', 'seller', null, null, 'Referral', 'Selling the Epping family home after 20 years; moving to Queensland. Wants a campaign over 6 weeks.'],
        ['helen', 'Helen Clarke', 'seller', null, null, 'Walk-in', 'Selling the Strathfield house to downsize. Flexible settlement.'],
        ['grace', 'Grace Kim', 'landlord', null, null, 'Domain', 'Owns the Parramatta apartment; selling with the tenant in place.'],
        ['liam', 'Liam Walsh', 'tenant', null, null, 'Open home', 'Looking to rent a 2-bedroom in Surry Hills or Redfern, up to $900 a week.'],
        ['emma', 'Emma Thompson', 'buyer', 2_700_000, 3_100_000, 'Referral', 'Multigenerational family. Needs 5 bedrooms or a granny flat for her parents; a pool would be a bonus. Strathfield or Burwood.'],
        ['ben', 'Ben Carter', 'investor', 2_000_000, 2_500_000, 'Domain', 'Wants commercial property with an existing long lease and at least a 5% net yield.'],
        ['chloe', 'Chloe Davis', 'buyer', 1_200_000, 1_350_000, 'Open home', 'Happy to renovate. Wants a house with a backyard in southern Sydney; solar panels a plus.'],
        ['noah', 'Noah Wilson', 'seller', null, null, 'realestate.com.au', 'Sold his Surry Hills terrace with us; may buy an investment apartment next year.'],
    ];

    /** [key, title, address, suburb, postcode, type, status, price, bed, bath, car, land sqm, owner key, description] */
    private const PROPERTIES = [
        ['epping-house', 'Family home with pool in Epping', '14 Kent Street', 'Epping', '2121', 'house', 'active', 1_850_000, 4, 2, 2, 695,
            'rajesh', 'Light-filled four-bedroom family home on a quiet street, zoned for Epping West Public and Cheltenham Girls. In-ground pool, north-facing backyard and a renovated kitchen with stone benchtops. Eight minutes walk to Epping station.'],
        ['chatswood-apt', 'Pet-friendly apartment near Chatswood station', '9/22 Help Street', 'Chatswood', '2067', 'apartment', 'active', 1_150_000, 2, 2, 1, null,
            null, 'Two-bedroom apartment with city skyline views in a pet-friendly building, three minutes walk to Chatswood station and Westfield. Secure parking and a storage cage.'],
        ['parramatta-apt', 'Investor apartment near Western Sydney University', '1204/5 Charles Street', 'Parramatta', '2150', 'apartment', 'active', 620_000, 1, 1, 1, null,
            'grace', 'One-bedroom apartment leased at $620 a week to a long-term tenant. Strong rental demand from Western Sydney University and Westmead Hospital. Strata levies under $1,000 a quarter.'],
        ['burwood-th', 'Renovated townhouse with courtyard in Burwood', '3/41 Belmore Street', 'Burwood', '2134', 'townhouse', 'sold', 1_420_000, 3, 2, 2, null,
            null, 'Low-maintenance three-bedroom townhouse with a private courtyard. Renovated kitchen, walk to Burwood station, Westfield and Burwood Road restaurants.'],
        ['strathfield-house', 'Five-bedroom home with granny flat in Strathfield', '7 Albyn Road', 'Strathfield', '2135', 'house', 'active', 2_950_000, 5, 3, 2, 1_020,
            'helen', 'Grand five-bedroom residence on a large block with a self-contained granny flat with separate access, ideal for multigenerational living. Solar-heated pool, close to Strathfield station and leading schools.'],
        ['hurstville-house', 'Renovator with duplex potential in Hurstville', '58 Croydon Road', 'Hurstville', '2220', 'house', 'active', 1_280_000, 3, 1, 1, 610,
            null, 'Original three-bedroom house on a level 610 sqm block. Solar panels, big backyard, and duplex potential subject to council approval. Renovate, extend or redevelop.'],
        ['surry-terrace', 'Character terrace in Surry Hills', '112 Riley Street', 'Surry Hills', '2010', 'house', 'sold', 1_650_000, 2, 1, 0, 110,
            'noah', 'Victorian terrace with original features and a sunny rear courtyard. Walk to Crown Street cafes, Central station and the city.'],
        ['bondi-apt', 'Beachside apartment in Bondi', '6/180 Campbell Parade', 'Bondi Beach', '2026', 'apartment', 'active', 1_750_000, 2, 1, 1, null,
            null, 'Two-bedroom apartment with ocean glimpses and lots of natural light, one minute walk to Bondi Beach and the coastal walk.'],
        ['parramatta-land', 'DA-approved duplex site in North Parramatta', '23 Gladstone Street', 'North Parramatta', '2151', 'land', 'active', 980_000, null, null, null, 560,
            null, 'Vacant 560 sqm block with DA-approved plans for a duplex. Close to Parramatta CBD, the light rail and schools. Ideal for builders and developers.'],
        ['chatswood-th', 'Townhouse with home office in Chatswood', '5/30 Victor Street', 'Chatswood', '2067', 'townhouse', 'draft', 1_690_000, 3, 2, 2, null,
            null, 'Three-bedroom townhouse with a dedicated home office, pet-friendly complex, in the Chatswood Public School catchment. Coming soon.'],
        ['epping-apt', 'Three-bedroom apartment with study in Epping', '402/8 Cambridge Street', 'Epping', '2121', 'apartment', 'active', 1_080_000, 3, 2, 2, null,
            null, 'Family-sized three-bedroom apartment plus study, two minutes walk to Epping station. Large balcony and a playground in the complex.'],
        ['burwood-shop', 'Leased shopfront on Burwood Road', '210 Burwood Road', 'Burwood', '2134', 'commercial', 'withdrawn', 2_200_000, null, 1, null, 180,
            null, 'Ground-floor retail shop with a national tenant on a 3-year lease, about 4.2% net yield.'],
    ];

    /** [title, contact, property, stage, value, created days ago, expected close in days, closed days ago, notes] */
    private const DEALS = [
        ['Purchase - Sharma', 'priya', 'epping-house', 'negotiation', 1_820_000, 40, 14, null,
            ['Inspected with the kids; they loved the pool.', 'Second inspection done. Building report clean.', 'Offer at $1.8m, vendor countered at $1.85m.']],
        ['Purchase - Wong', 'daniel', 'chatswood-apt', 'offer', 1_120_000, 25, 21, null,
            ['Confirmed the building allows dogs.', 'Finance pre-approval confirmed.', 'Offer submitted subject to strata report.']],
        ['Investment - Bennett', 'olivia', 'parramatta-apt', 'inspection', 610_000, 10, 30, null,
            ['Sent the lease and rental ledger.', 'Inspection booked for Saturday 10am.']],
        ['Purchase - Rossi', 'marco', 'burwood-th', 'won', 1_400_000, 60, null, 5,
            ['Loved the courtyard and the walk to the station.', 'Offer accepted at $1.4m.', 'Contracts exchanged.']],
        ['Development site - O\'Connor', 'james', 'parramatta-land', 'contacted', 950_000, 7, 45, null,
            ['Sent the DA plans and council conditions.']],
        ['Purchase - Rahman', 'aisha', 'chatswood-th', 'lead', 1_650_000, 3, 60, null,
            ['Enquiry from the coming-soon listing; asked about the study size.']],
        ['Purchase - Nguyen', 'tom', 'epping-apt', 'inspection', 1_060_000, 14, 30, null,
            ['Family inspection went well.', 'Waiting on their mortgage broker.']],
        ['Purchase - Martin', 'sophie', 'bondi-apt', 'lead', 1_700_000, 2, 45, null,
            ['Asked for a video walkthrough before flying up from Melbourne.']],
        ['Purchase - Thompson', 'emma', 'strathfield-house', 'offer', 2_900_000, 30, 20, null,
            ['Parents inspected the granny flat; very keen.', 'Asked for granny flat approval documents.', 'Offer at $2.9m submitted.']],
        ['Investment - Carter', 'ben', 'burwood-shop', 'lost', 2_150_000, 80, null, 20,
            ['Interested in the yield.', 'Lease only 3 years and yield under 5%; walked away.']],
        ['Purchase - Davis', 'chloe', 'hurstville-house', 'negotiation', 1_250_000, 21, -3, null,
            ['Loves the backyard and the solar panels.', "Builder's report found roof repairs; negotiating the price."]],
        ['Sale listing - Patel', 'rajesh', 'epping-house', 'won', 1_850_000, 90, null, 70,
            ['Appraisal at $1.8m to $1.9m.', 'Listing agreement signed; 6-week campaign.']],
        ['Sale listing - Clarke', 'helen', 'strathfield-house', 'won', 2_950_000, 75, null, 50,
            ['Listing agreement signed.']],
        ['Sale - Wilson terrace', 'noah', 'surry-terrace', 'won', 1_650_000, 65, null, 15,
            ['Auction campaign started.', 'Sold at auction for $1.65m.']],
        ['Rental placement - Walsh', 'liam', null, 'contacted', 46_800, 5, 14, null,
            ['Sent two Surry Hills rentals within budget.']],
        ['Sale listing - Kim', 'grace', 'parramatta-apt', 'won', 620_000, 55, null, 40,
            ['Agreed to sell with the tenant in place.']],
        ['Purchase - Wong (Epping)', 'daniel', 'epping-apt', 'lost', 1_050_000, 70, null, 40,
            ['Outbid by $40k at the deadline.']],
        ['Investment - Bennett (land)', 'olivia', 'parramatta-land', 'lost', 900_000, 50, null, 30,
            ['Holding costs too high for her yield target; not proceeding.']],
        ['Purchase - Sharma (Strathfield)', 'priya', 'strathfield-house', 'lost', 2_800_000, 120, null, 100,
            ['Well over budget once stamp duty was included.']],
        ['Purchase - Nguyen (Chatswood)', 'tom', 'chatswood-apt', 'lost', 1_150_000, 45, null, 25,
            ['Needs 3 bedrooms; two is too small.']],
        ['Beachside search - Martin', 'sophie', null, 'contacted', 1_750_000, 6, 60, null,
            ['Sent three off-market beachside listings.']],
        ['Duplex site - O\'Connor (Hurstville)', 'james', 'hurstville-house', 'lead', 1_250_000, 4, 60, null,
            ['Interested in duplex potential; wants a feasibility study first.']],
    ];
}
