import 'dotenv/config';

import { createPostgresClient } from '../lib/data/db';
import { loadSeedCoupons } from '../lib/data/repositories/couponRepository';
import { loadSeedFailureScenarios } from '../lib/data/repositories/failureScenarioRepository';
import { loadSeedMenus } from '../lib/data/repositories/menuRepository';
import { loadSeedPois } from '../lib/data/repositories/poiRepository';
import { loadSeedRoutes } from '../lib/data/repositories/routeRepository';

async function main() {
  const pois = await loadSeedPois();
  const coupons = await loadSeedCoupons();
  const menus = await loadSeedMenus();
  const routes = await loadSeedRoutes();
  const failures = await loadSeedFailureScenarios();
  const sql = await createPostgresClient();

  if (!sql) {
    console.log(`Loaded seeds only: ${pois.length} POIs, ${coupons.length} coupons, ${menus.length} menu items, ${routes.length} routes, ${failures.length} failure scenarios.`);
    return;
  }

  await sql.begin(async (tx) => {
    for (const poi of pois) {
      await tx`
        INSERT INTO pois (
          id, name, category, location, distance_km, open_hours, rating, review_count, avg_price, tags,
          wait_minutes, booking_supported, availability, source, reason, risk_tags, supported_scenarios,
          audience, district, menu_summary, review_summary, capacity, min_child_age, max_party_size
        )
        VALUES (
          ${poi.id}, ${poi.name}, ${poi.category}, ST_SetSRID(ST_MakePoint(${poi.lng}, ${poi.lat}), 4326)::geography,
          ${poi.distance_km}, ${JSON.stringify(poi.open_hours)}::jsonb, ${poi.rating}, ${poi.review_count}, ${poi.avg_price}, ${poi.tags},
          ${poi.wait_minutes}, ${poi.booking_supported}, ${JSON.stringify(poi.availability)}::jsonb, ${poi.source}, ${poi.reason},
          ${poi.risk_tags}, ${poi.supported_scenarios}, ${poi.audience}, ${poi.district}, ${poi.menu_summary},
          ${poi.review_summary}, ${poi.capacity}, ${poi.min_child_age}, ${poi.max_party_size}
        )
        ON CONFLICT (id) DO NOTHING
      `;
    }

    for (const coupon of coupons) {
      await tx`
        INSERT INTO coupons (id, poi_id, title, discount_type, value, valid_until, rules)
        VALUES (${coupon.id}, ${coupon.poi_id}, ${coupon.title}, ${coupon.discount_type}, ${coupon.value}, ${coupon.valid_until}, ${coupon.rules})
        ON CONFLICT (id) DO NOTHING
      `;
    }

    for (const item of menus) {
      await tx`
        INSERT INTO menus (id, poi_id, name, price, tags, allergens, nutrition_note)
        VALUES (${item.id}, ${item.poi_id}, ${item.name}, ${item.price}, ${item.tags}, ${item.allergens}, ${item.nutrition_note})
        ON CONFLICT (id) DO NOTHING
      `;
    }

    for (const route of routes) {
      await tx`
        INSERT INTO route_legs (from_poi_id, to_poi_id, mode, duration_minutes, distance_km, polyline, route_summary)
        VALUES (${route.from}, ${route.to}, ${route.mode}, ${route.duration_minutes}, ${route.distance_km}, ${route.polyline}, ${route.route_summary})
        ON CONFLICT (from_poi_id, to_poi_id, mode) DO NOTHING
      `;
    }

    for (const failure of failures) {
      await tx`
        INSERT INTO failure_scenarios (id, type, target_id, trigger, replacement_strategy, user_message)
        VALUES (${failure.id}, ${failure.type}, ${failure.target_id}, ${failure.trigger}, ${failure.replacement_strategy}, ${failure.user_message})
        ON CONFLICT (id) DO NOTHING
      `;
    }
  });

  await sql.end();
  console.log(`Seeded ${pois.length} POIs, ${coupons.length} coupons, ${menus.length} menu items, ${routes.length} routes, ${failures.length} failure scenarios.`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
