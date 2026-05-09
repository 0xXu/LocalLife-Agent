import { searchPois } from '../data/repositories/poiRepository';
import { readOnlyTool } from './common';

export const searchRestaurantsTool = readOnlyTool('search_restaurants', async (input) => ({
  restaurants: await searchPois({ category: 'restaurant', scenario: input.scenario ?? 'family', radiusKm: input.radiusKm ?? 5, tags: input.tags ?? [] }),
}));
