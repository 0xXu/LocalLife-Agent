import { readSeedFile, type FailureScenario } from '../db';

export async function loadSeedFailureScenarios(): Promise<FailureScenario[]> {
  return readSeedFile<FailureScenario[]>('failureScenarios.json');
}
