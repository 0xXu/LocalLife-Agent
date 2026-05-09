import { jsonRoute } from '../_shared';
import { getHealth } from '../../../lib/server/planningService';

export function GET() {
  return jsonRoute(() => getHealth());
}
