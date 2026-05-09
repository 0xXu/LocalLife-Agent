import { sideEffectTool } from './common';

export const reserveActivityTool = sideEffectTool('reserve_activity', 'TKT', (input) => ({
  ticket_id: input.ticket_id ?? 'ticket_seed',
  place_id: input.place_id,
  party_size: input.party_size,
  time: input.time,
}));
