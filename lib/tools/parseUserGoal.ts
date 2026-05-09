import { readOnlyTool } from './common';

export const parseUserGoalTool = readOnlyTool('parse_user_goal', async (input) => ({
  scenario: input.goal?.includes('雨') ? 'rainy_indoor' : 'family',
  goal_length: String(input.goal ?? '').length,
}));
