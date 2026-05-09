import { checkAvailability } from '../data/repositories/availabilityRepository';
import { readOnlyTool } from './common';

export const checkAvailabilityTool = readOnlyTool('check_availability', async (input) => checkAvailability({
  placeId: input.place_id ?? input.placeId,
  time: input.time,
  partySize: input.party_size ?? input.partySize ?? 1,
}));
