import { readSeedFile, type MenuItem } from '../db';

export async function loadSeedMenus(): Promise<MenuItem[]> {
  return readSeedFile<MenuItem[]>('menus.json');
}

export async function searchMenuByPoi(poiId: string): Promise<MenuItem[]> {
  return (await loadSeedMenus()).filter((item) => item.poi_id === poiId);
}

export const getMenuForPoi = searchMenuByPoi;
