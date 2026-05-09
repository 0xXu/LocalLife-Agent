export function ensureKnownPlaceIds(plan: { itinerary?: Array<{ place_id?: string }> }, knownPlaceIds: Set<string>) {
  for (const step of plan.itinerary ?? []) {
    if (step.place_id && !knownPlaceIds.has(step.place_id)) {
      throw new Error(`unknown_place_id:${step.place_id}`);
    }
  }
}

export function ensureConfirmationSnapshot(options: { confirmed?: boolean; confirmationSnapshot?: unknown }) {
  if (options.confirmed === true && !options.confirmationSnapshot) {
    throw new Error('confirmation_snapshot_required');
  }
}
