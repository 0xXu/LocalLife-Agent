import { readOnlyTool } from './common';

export const buildItineraryTool = readOnlyTool('build_itinerary', async (input) => ({
  itinerary: input.itinerary ?? [],
  status: 'draft',
}));
