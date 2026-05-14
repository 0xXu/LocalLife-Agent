import test from 'node:test';
import assert from 'node:assert/strict';

import { getActionKey } from '../../features/planner/usePlanMachine';

test('getActionKey prefers backend durable action_id for graph resume decisions', () => {
  assert.equal(
    getActionKey({
      action_id: 'act_msg_001',
      id: 'legacy_message_id',
      tool: 'messaging',
      type: 'send_plan_message',
    }),
    'act_msg_001',
  );
});
