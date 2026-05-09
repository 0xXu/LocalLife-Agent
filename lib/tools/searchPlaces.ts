import { searchPois } from '../data/repositories/poiRepository';
import { readOnlyTool } from './common';

export const searchPlacesTool = readOnlyTool('search_places', async (input) => ({
  places: await searchPois({ scenario: input.scenario ?? 'family', radiusKm: input.radiusKm ?? 5, tags: input.tags ?? [] }),
}));
