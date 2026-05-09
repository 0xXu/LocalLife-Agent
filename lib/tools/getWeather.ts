import { readOnlyTool } from './common';

export const getWeatherTool = readOnlyTool('get_weather', async () => ({
  condition: 'cloudy',
  rain_probability: 0.2,
  source: 'local_seed',
}));
