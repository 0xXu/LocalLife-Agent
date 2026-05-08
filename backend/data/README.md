# Local Data Layer

`catalog.py` builds a deterministic local catalog for demo stability:

- 90 POIs across family, friends, date, rainy indoor, restaurants, and dessert walk categories.
- 24 coupons/deals.
- Menu items for restaurant ordering.
- Weather fixtures for clear and rainy scenarios.
- Route matrix entries for local route optimization.
- Failure scenarios for restaurant unavailable, activity full, rain, route timeout, and budget overrun.

The generator keeps the repo compact while still exposing a complete data layer to tests and backend tools.
