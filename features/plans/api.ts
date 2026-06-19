import type { PlanListResponse } from '../../types/api';
import type { PlanResponse } from '../../types/weekendpilot';
import { apiRequest } from '../../lib/api/client';

export async function getPlan(planId: string) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}`);
}

export async function listPlans() {
  return apiRequest<PlanListResponse>('/api/plans');
}
