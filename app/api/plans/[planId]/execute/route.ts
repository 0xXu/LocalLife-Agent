import { jsonRoute, planIdFrom } from '../../../_shared';
import { executePlan } from '../../../../../lib/server/planningService';

export async function POST(request: Request, context: { params: Promise<{ planId: string }> }) {
  return jsonRoute(async () => {
    const body = await request.json();
    return executePlan(await planIdFrom(context), body.confirmed === true);
  });
}
