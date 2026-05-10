import { NextResponse } from 'next/server';
import { PlanningServiceError } from '../../lib/server/planningService';

// Deprecated compatibility routes: the frontend now calls the FastAPI backend
// through NEXT_PUBLIC_API_URL instead of these Next.js API handlers.
const statusByCode: Record<string, number> = {
  validation_error: 400,
  confirmation_required: 403,
  plan_not_found: 404,
  tool_failed: 500,
};

export async function jsonRoute<T>(handler: () => T | Promise<T>) {
  try {
    return NextResponse.json(await handler());
  } catch (error) {
    if (error instanceof PlanningServiceError) {
      return NextResponse.json(
        { error: { code: error.code, message: error.message } },
        { status: statusByCode[error.code] ?? 500 },
      );
    }

    return NextResponse.json(
      { error: { code: 'tool_failed', message: error instanceof Error ? error.message : 'Unknown error' } },
      { status: 500 },
    );
  }
}

export async function planIdFrom(context: { params: Promise<{ planId: string }> }) {
  const params = await context.params;
  return params.planId;
}
