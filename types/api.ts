// types/api.ts

export type PlanStatus = 'draft' | 'saved' | 'executing' | 'completed';
export type ActivityStatus = 'completed' | 'failed' | 'partial';

export interface PlanSummary {
  id: string;
  title: string;
  status: PlanStatus;
  summary: string;
  created_at: string;
  updated_at: string;
  tags: string[];
  location?: string;
  estimated_cost?: string;
  itinerary_count: number;
}

export interface PlanListResponse {
  plans: PlanSummary[];
  total: number;
}

export interface ActivityRecord {
  id: string;
  plan_id: string;
  plan_title: string;
  executed_at: string;
  status: ActivityStatus;
  total_cost?: string;
  receipts: ActivityReceipt[];
  summary: string;
}

export interface ActivityReceipt {
  type: string;
  tool: string;
  id: string;
  status: string;
  detail: string;
}

export interface ActivityStats {
  total_plans: number;
  total_cost: number;
  frequent_type: string;
}

export interface ActivityListResponse {
  activities: ActivityRecord[];
  stats: ActivityStats;
}

export interface UserPreferences {
  profile: {
    display_name: string;
    email: string;
    avatar_url?: string;
  };
  diet: {
    fitness_friendly: boolean;
    vegetarian: boolean;
    gluten_free: boolean;
    allergies: string[];
  };
  location: {
    radius_km: number;
    home_address?: string;
    favorite_places: string[];
  };
  notifications: {
    execution_reminder: boolean;
    plan_change: boolean;
    weekly_digest: boolean;
  };
}
