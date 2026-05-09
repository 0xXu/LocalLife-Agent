import { sideEffectTool } from './common';

export const createCalendarEventTool = sideEffectTool('create_calendar_event', 'CAL', (input) => ({
  event_id: input.event_id ?? 'calendar_seed',
  title: input.title ?? 'WeekendPilot plan',
  participants: input.participants ?? [],
}));
