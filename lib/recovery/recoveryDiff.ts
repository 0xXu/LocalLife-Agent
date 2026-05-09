export function preservedTitles(itinerary: Array<Record<string, any>>, changedType: string) {
  return itinerary
    .filter((step) => step.type !== changedType && step.category !== changedType)
    .map((step) => String(step.title));
}

export function replaceFirstByType(itinerary: Array<Record<string, any>>, type: string, replacement: Record<string, any>) {
  let replaced = false;
  return itinerary.map((step) => {
    if (!replaced && (step.type === type || step.category === type)) {
      replaced = true;
      return { ...step, ...replacement };
    }
    return step;
  });
}
