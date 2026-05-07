export const demoTools = [
  'parse_user_goal',
  'search_places',
  'search_restaurants',
  'rank_candidates',
  'optimize_route',
  'check_availability',
  'create_reservation',
  'send_plan_message'
];

const activity = {
  placeId: 'act_001',
  title: 'City Science Museum',
  category: 'family_activity',
  start: '13:30',
  end: '15:30',
  cost: '$45 est.',
  travel: '12 min drive',
  reason: 'Features the Little Explorers exhibit, indoor route, and easy walking for a 5-year-old.'
};

const primaryRestaurant = {
  placeId: 'res_014',
  title: 'Green Canopy Cafe',
  category: 'restaurant',
  start: '15:45',
  end: '16:45',
  cost: '$42 est.',
  travel: '5 min walk from museum',
  reason: 'Fresh salads, grilled lean proteins, low-fat menu markers, and kid-friendly seating.'
};

const fallbackRestaurant = {
  placeId: 'res_022',
  title: 'Light Bowl Bistro',
  category: 'restaurant',
  start: '15:50',
  end: '16:50',
  cost: '$48 est.',
  travel: '7 min walk from museum',
  reason: 'Similar low-fat meals and a confirmed 16:00 slot after the primary restaurant became unavailable.'
};

const dessertWalk = {
  placeId: 'walk_006',
  title: 'Riverside Low-Sugar Dessert Walk',
  category: 'dessert_walk',
  start: '17:00',
  end: '17:30',
  cost: '$18 est.',
  travel: '1.2 km relaxed walk',
  reason: 'Short post-meal walk with a low-sugar drink option and a direct route home.'
};

export function buildPlan(goalText = '') {
  const constraints = {
    party: goalText.match(/5\s*y?o|5岁|kid|child/i) ? '2 adults, 1 child (5yo)' : '2 adults',
    duration: '~4.5 hours',
    dietary: goalText.match(/diet|low[-\s]?fat|减肥|减脂/i) ? 'low-fat' : 'balanced',
    radiusKm: goalText.match(/not too far|nearby|别.*远|5km/i) ? 5 : 8,
    transport: 'taxi + walking'
  };

  const itinerary = [activity, primaryRestaurant, dessertWalk].map((step) => ({ ...step }));
  const plan = {
    id: 'plan_family_001',
    status: 'ready_for_confirmation',
    title: 'Interactive & Healthy Family Afternoon',
    summary: 'Science museum, low-fat cafe, and short riverside dessert walk.',
    constraints,
    itinerary,
    overview: {
      totalDuration: '4h 00m',
      driveTime: '~25 min',
      walkingDistance: '1.2 km',
      estimatedCost: '$85 - $110'
    }
  };

  const trace = [
    traceStep('parse_user_goal', 'Parsed people, diet, radius, and half-day duration.', 'ok'),
    traceStep('search_places', 'Found family-friendly indoor/outdoor venues within 5km.', 'ok'),
    traceStep('search_restaurants', 'Cross-referenced nearby dining with low-fat menu indicators.', 'ok'),
    traceStep('rank_candidates', 'Ranked candidates by distance, child fit, diet fit, wait time, and cost.', 'ok'),
    traceStep('optimize_route', 'Generated museum -> cafe -> riverside route.', 'ok'),
    traceStep('check_availability', 'Green Canopy Cafe has a mock 15:45 slot for 3 people.', 'ok')
  ];

  return {
    constraints,
    trace,
    itinerary,
    plan
  };
}

export function executePlan(plan) {
  const targetPlan = plan ?? buildPlan().plan;

  return [
    {
      type: 'activity_reservation',
      tool: 'create_reservation',
      id: 'TKT-2041',
      status: 'confirmed',
      detail: `${targetPlan.itinerary[0].title} reserved for 3 guests.`
    },
    {
      type: 'restaurant_reservation',
      tool: 'create_reservation',
      id: restaurantReceiptId(targetPlan.itinerary[1].placeId),
      status: 'confirmed',
      detail: `${targetPlan.itinerary[1].title} table confirmed at ${targetPlan.itinerary[1].start}.`
    },
    {
      type: 'message',
      tool: 'send_plan_message',
      id: 'MSG-9128',
      status: 'sent',
      detail: 'Plan summary sent to family chat.'
    }
  ];
}

export function recoverUnavailableRestaurant(plan) {
  const original = plan ?? buildPlan().plan;
  const itinerary = original.itinerary.map((step, index) => (
    index === 1 ? { ...fallbackRestaurant } : { ...step }
  ));

  return {
    ...original,
    id: 'plan_family_001_recovered',
    status: 'recovered_pending_confirmation',
    itinerary,
    diff: {
      changed: 'restaurant',
      reason: 'Green Canopy Cafe returned available=false for the requested slot.',
      from: original.itinerary[1].title,
      to: fallbackRestaurant.title,
      costDelta: '+$6',
      travelDelta: '+2 min walk',
      preserved: [original.itinerary[0].title, original.itinerary[2].title]
    }
  };
}

function traceStep(tool, message, status) {
  return {
    tool,
    status,
    message,
    durationMs: tool === 'parse_user_goal' ? 120 : 260
  };
}

function restaurantReceiptId(placeId) {
  return placeId === fallbackRestaurant.placeId ? 'RES-7420' : 'RES-3812';
}
