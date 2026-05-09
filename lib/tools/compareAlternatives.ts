import { readOnlyTool } from './common';

export const compareAlternativesTool = readOnlyTool('compare_alternatives', async (input) => ({
  changed: input.changed ?? 'none',
  alternatives: input.alternatives ?? [],
}));
