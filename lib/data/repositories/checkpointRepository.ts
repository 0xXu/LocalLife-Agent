import type { PlannerCheckpointer, PlannerState } from '../../agent/state';

export type CheckpointRecord = {
  thread_id: string;
  status: string;
  state_json: Record<string, any>;
  created_at?: string;
  updated_at?: string;
};

export type CheckpointRepository = {
  save(record: CheckpointRecord): Promise<CheckpointRecord>;
  load(threadId: string): Promise<CheckpointRecord | undefined>;
};

export function createTestCheckpointRepository(initial: CheckpointRecord[] = []): CheckpointRepository {
  const records = new Map(initial.map((record) => [record.thread_id, clone(record)]));
  return {
    async save(record) {
      const now = new Date().toISOString();
      const next = {
        ...clone(record),
        created_at: record.created_at ?? records.get(record.thread_id)?.created_at ?? now,
        updated_at: now,
      };
      records.set(record.thread_id, next);
      return clone(next);
    },
    async load(threadId) {
      return clone(records.get(threadId));
    },
  };
}

export function createCheckpointerAdapter(repository: CheckpointRepository): PlannerCheckpointer {
  return {
    async get(threadId: string) {
      const record = await repository.load(threadId);
      return record?.state_json as PlannerState | undefined;
    },
    async put(threadId: string, state: PlannerState) {
      await repository.save({
        thread_id: threadId,
        status: state.status,
        state_json: state as unknown as Record<string, any>,
      });
    },
  };
}

function clone<T>(value: T): T {
  return value === undefined ? value : JSON.parse(JSON.stringify(value));
}
