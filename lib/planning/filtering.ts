export type RejectionReason =
  | 'closed_at_requested_time'
  | 'outside_radius'
  | 'age_mismatch'
  | 'capacity_mismatch'
  | 'wait_exceeds_threshold';

export type RejectedCandidate = {
  place_id: string;
  name: string;
  reason: RejectionReason;
};

export type FilterInput = {
  date: string;
  time: string;
  radiusKm: number;
  childAges: number[];
  partySize: number;
  maxWaitMinutes: number;
};

export type FilterablePoi = {
  id: string;
  name: string;
  distance_km: number;
  wait_minutes: number;
  open_hours: unknown;
  min_child_age?: number;
  max_party_size?: number;
};

export type FilteredCandidates<T> = T[] & { rejected: RejectedCandidate[] };

export function hardFilterCandidates<T extends FilterablePoi>(candidates: T[], input: FilterInput): FilteredCandidates<T> {
  const kept: T[] = [];
  const rejected: RejectedCandidate[] = [];

  for (const candidate of candidates) {
    const reason = rejectionReason(candidate, input);
    if (reason) {
      rejected.push({ place_id: candidate.id, name: candidate.name, reason });
    } else {
      kept.push(candidate);
    }
  }

  return Object.assign(kept, { rejected });
}

function rejectionReason(candidate: FilterablePoi, input: FilterInput): RejectionReason | null {
  if (!isOpenAt(candidate.open_hours, input.date, input.time)) {
    return 'closed_at_requested_time';
  }

  if (candidate.distance_km > input.radiusKm) {
    return 'outside_radius';
  }

  const minChildAge = candidate.min_child_age ?? 0;
  if (input.childAges.some((age) => age < minChildAge)) {
    return 'age_mismatch';
  }

  const maxPartySize = candidate.max_party_size ?? Number.POSITIVE_INFINITY;
  if (input.partySize > maxPartySize) {
    return 'capacity_mismatch';
  }

  if (candidate.wait_minutes > input.maxWaitMinutes) {
    return 'wait_exceeds_threshold';
  }

  return null;
}

function isOpenAt(openHours: unknown, date: string, time: string) {
  const day = dayKey(date);
  if (Array.isArray(openHours)) {
    return openHours.some((hours) => {
      if (!hours || typeof hours !== 'object') {
        return false;
      }
      const record = hours as { day?: string; start?: string; end?: string };
      return (!record.day || record.day === day) && within(time, record.start, record.end);
    });
  }

  if (openHours && typeof openHours === 'object') {
    const record = openHours as Record<string, unknown>;
    const dayHours = record[day] ?? record.weekday ?? record.saturday ?? record.sunday;
    if (dayHours && typeof dayHours === 'object') {
      const hours = dayHours as { start?: string; end?: string };
      return within(time, hours.start, hours.end);
    }
  }

  return true;
}

function dayKey(date: string) {
  const day = new Date(`${date}T00:00:00+09:00`).getDay();
  if (day === 0) {
    return 'sunday';
  }
  if (day === 6) {
    return 'saturday';
  }
  return 'weekday';
}

function within(time: string, start = '00:00', end = '23:59') {
  return toMinutes(time) >= toMinutes(start) && toMinutes(time) <= toMinutes(end);
}

function toMinutes(value: string) {
  const [hours = '0', minutes = '0'] = value.split(':');
  return Number(hours) * 60 + Number(minutes);
}
