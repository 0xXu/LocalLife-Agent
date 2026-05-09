import { jsonRoute, planIdFrom } from '../../../_shared';
import { patchConstraints } from '../../../../../lib/server/planningService';

export async function PATCH(request: Request, context: { params: Promise<{ planId: string }> }) {
  return jsonRoute(async () => {
    const body = await request.json();
    return patchConstraints(await planIdFrom(context), body);
  });
}
