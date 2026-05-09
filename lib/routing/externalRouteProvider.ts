import type { RouteProvider } from './routeProvider';
import { localRouteProvider } from './localRouteProvider';

export function createExternalRouteProvider(): RouteProvider {
  return {
    async optimize(input) {
      return localRouteProvider.optimize(input);
    },
  };
}
