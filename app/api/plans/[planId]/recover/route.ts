import { jsonRoute, planIdFrom } from '../../../_shared';
import { recoverPlan } from '../../../../../lib/server/planningService';

export async function POST(request: Request, context: { params: Promise<{ planId: string }> }) {
  return jsonRoute(async () => {
    const body = await request.json();
    return recoverPlan(await planIdFrom(context), String(body.reason ?? ''));
  });
}
