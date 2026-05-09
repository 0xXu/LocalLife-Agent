import { sideEffectTool } from './common';

export const createReservationTool = sideEffectTool('create_reservation', 'RES', (input) => ({
  reservation_id: input.reservation_id ?? 'reservation_seed',
  place_id: input.place_id,
  party_size: input.party_size,
  time: input.time,
  phone_tail: input.phone_tail ?? '1234',
}));
