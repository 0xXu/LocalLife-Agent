import { localRouteProvider } from '../routing/localRouteProvider';
import { readOnlyTool } from './common';

export const optimizeRouteTool = readOnlyTool('optimize_route', async (input) => localRouteProvider.optimize({
  origin: input.origin,
  waypoints: input.waypoints ?? [],
  mode: input.mode ?? 'walk_taxi',
}));
