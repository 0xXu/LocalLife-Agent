import type { AvailabilityResult } from '../db';
import { getPoi } from './poiRepository';

export type AvailabilityInput = {
  placeId: string;
  time: string;
  partySize: number;
};

export async function checkAvailability(input: AvailabilityInput): Promise<AvailabilityResult> {
  const poi = await getPoi(input.placeId);
  const slot = poi.availability.slots?.find((item) => item.time === input.time);
  const blackedOut = poi.availability.blackout_times?.includes(input.time) ?? false;
  const remaining = slot?.remaining ?? (slot as { remaining_capacity?: number } | undefined)?.remaining_capacity ?? poi.capacity;
  const available = !blackedOut && input.partySize <= poi.max_party_size && input.partySize <= remaining && (slot?.available ?? poi.availability.default ?? true);

  return {
    place_id: poi.id,
    available,
    wait_minutes: available ? poi.wait_minutes : Math.max(poi.wait_minutes, 30),
    remaining_capacity: Math.max(remaining - input.partySize, 0),
    source: 'seed',
  };
}
