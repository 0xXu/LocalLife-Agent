import { readSeedFile, type LocalLifeScenario, type Poi, type PoiCategory } from '../db';

export type PoiSearchInput = {
  category?: PoiCategory | 'restaurant';
  scenario?: LocalLifeScenario;
  radiusKm: number;
  tags: string[];
};

export async function loadSeedPois(): Promise<Poi[]> {
  return readSeedFile<Poi[]>('pois.json');
}

export async function searchPois(input: PoiSearchInput): Promise<Poi[]> {
  const pois = await loadSeedPois();
  return pois
    .filter((poi) => (input.category ? poi.category === input.category : true))
    .filter((poi) => (input.scenario ? poi.supported_scenarios.includes(input.scenario) : true))
    .filter((poi) => poi.distance_km <= input.radiusKm)
    .filter((poi) => input.tags.every((tag) => poi.tags.includes(tag) || poi.menu_summary.includes(tag)))
    .sort((left, right) => right.rating - left.rating || left.distance_km - right.distance_km);
}

export async function getPoi(id: string): Promise<Poi> {
  const poi = (await loadSeedPois()).find((item) => item.id === id);
  if (!poi) {
    throw new Error(`poi_not_found:${id}`);
  }
  return poi;
}
