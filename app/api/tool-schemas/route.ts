import { jsonRoute } from '../_shared';
import { getToolSchemas } from '../../../lib/server/planningService';

export function GET() {
  return jsonRoute(() => getToolSchemas());
}
