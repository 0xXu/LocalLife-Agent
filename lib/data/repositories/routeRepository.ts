import { readSeedFile, type RouteLeg } from '../db';

export async function loadSeedRoutes(): Promise<RouteLeg[]> {
  return readSeedFile<RouteLeg[]>('routes.json');
}

export async function getRouteLegs(waypoints: string[]): Promise<RouteLeg[]> {
  const routes = await loadSeedRoutes();
  const pairs = waypoints.slice(0, -1).map((from, index) => [from, waypoints[index + 1]]);
  return pairs.map(([from, to]) => {
    const route = routes.find((item) => item.from === from && item.to === to);
    if (!route) {
      throw new Error(`route_leg_not_found:${from}:${to}`);
    }
    return route;
  });
}
