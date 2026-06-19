import { apiRequest } from '../../lib/api/client';

export interface BackendUserPreference {
  key: string;
  value: unknown;
  source: string;
  confidence: number;
  scope: string;
  evidence: string;
  expires_at: string;
  user_editable: boolean;
  sensitive: boolean;
}

export interface BackendUserProfile {
  user_id: string;
  explicit_preferences: BackendUserPreference[];
  learned_preferences: BackendUserPreference[];
  session_preferences: BackendUserPreference[];
}

export async function getUserProfile(userId: string) {
  return apiRequest<BackendUserProfile>(`/api/users/${userId}/profile`);
}

export async function saveUserProfile(userId: string, profile: BackendUserProfile) {
  return apiRequest<BackendUserProfile>(`/api/users/${userId}/profile`, {
    method: 'POST',
    body: profile as unknown as Record<string, unknown>,
  });
}
