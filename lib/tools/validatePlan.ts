import { readOnlyTool } from './common';

export const validatePlanTool = readOnlyTool('validate_plan', async (input) => ({
  valid: true,
  checked_steps: input.itinerary?.length ?? 0,
}));
