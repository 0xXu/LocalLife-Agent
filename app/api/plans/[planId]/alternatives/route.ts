import { jsonRoute, planIdFrom } from '../../../_shared';
import { buildAlternatives } from '../../../../../lib/server/planningService';

export async function POST(_request: Request, context: { params: Promise<{ planId: string }> }) {
  return jsonRoute(async () => buildAlternatives(await planIdFrom(context)));
}
