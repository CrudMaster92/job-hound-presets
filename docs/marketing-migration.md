# Marketing migration ledger

The Marketing Agencies — Canada collection is migrating in two phases. Company
identity files are authored once so parent relationships, aliases, and
specialties remain stable while their monitor recipes are converted.

## Proposed initial phase

The initial collection contains 51 independently selectable companies using
deterministic Greenhouse, Lever, SmartRecruiters, DirectEmployers, Workday,
Jobvite, Publicis shared-feed, and dentsu shared-feed recipes. It also includes
the existing Omnicom Group identity, which belongs to the Fortune collection
but has no validated group-wide monitor. The Marketing monitors remain
`unverified` while current source results and employer ownership are reviewed.

The Fortune collection's Mosaic is a mining company. Mosaic Canada is a distinct
marketing agency with its own identity and monitor. No scraper recipe is copied
between collections. Acosta, ActionLink, and Mosaic Canada use the source's
Canadian agency listing paths and an exact `country_short = CAN` filter. CORE
Foodservice and Premium are held back because their draft JSON feeds returned
other Acosta-family agencies' jobs. Viral Nation's source descriptions are
temporarily omitted because JobHound's current salary inference rejected some
of that text; titles, locations, and direct source URLs remain available.

Publicis and dentsu child companies share a `source_key` within their respective
feeds. JobHound can therefore reuse a bounded response while applying each
company's typed ownership predicates independently. Existing JobHound recipes
remain authoritative when a company is already installed or later appears in
another collection.

On September 29, 2026, all 51 included recipes completed a live JobHound
runtime run without an execution error. Forty-one returned jobs and ten returned
zero current jobs: BBDO Canada, Critical Mass, DDB Canada, GALE, Klick Health,
Léger, NIQ Canada, Ogilvy Canada, OLIVER Canada, and Zulu Alpha Kilo. The
monitor files record those point-in-time counts as `unverified` observations.
Acosta, ActionLink, and Mosaic Canada's live source job IDs were disjoint.
Company ownership and source completeness still need reviewer sign-off before
any monitor is labelled `verified`.

## Specialized collector backlog

These 30 enabled source entries retain identity metadata and explicit
`unavailable` status. They have no published monitor or Marketing collection
membership until their specialized collectors are converted and validated:

Direct JSON feeds that still need safe listing/detail composition:

- Bond Brand Loyalty
- Brand Momentum
- Circana Canada
- Cossette
- Ipsos Canada
- Kognitive
- LG2
- MCA
- Rethink
- We Are Social Canada

LinkedIn-backed collectors that need a permitted, deterministic first-party
replacement before publication:

- Havas Canada
- Hearts & Science Canada
- Initiative Canada
- Kinesso Canada
- Media Experts
- Mediahub Worldwide Canada
- MRM Canada
- OMD Canada
- PHD Canada
- Touché Canada
- UM Canada

Site-specific HTML, WordPress, Job Bank, or browser collectors:

- Gainshare
- Influence Marketing
- Match Retail
- OSL Retail Services
- PromoStaff
- Veritas Communications
- XMC

Acosta-family feeds requiring employer-ownership repair:

- CORE Foodservice
- Premium

## Disabled source entries

TBWA Canada, McCann Canada, Sid Lee Media, and Craft Worldwide Canada remain
disabled and are not authored or published.
