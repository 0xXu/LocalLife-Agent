import { jsonRoute, planIdFrom } from '../../../_shared';
import { confirmPlan } from '../../../../../lib/server/planningService';

export async function POST(request: Request, context: { params: Promise<{ planId: string }> }) {
  return jsonRoute(async () => {
    const body = await request.json();
    return confirmPlan(await planIdFrom(context), body.confirmed === true);
  });
}
