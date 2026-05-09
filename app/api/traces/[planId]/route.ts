import { jsonRoute, planIdFrom } from '../../_shared';
import { getTraces } from '../../../../lib/server/planningService';

export async function GET(_request: Request, context: { params: Promise<{ planId: string }> }) {
  return jsonRoute(async () => getTraces(await planIdFrom(context)));
}
