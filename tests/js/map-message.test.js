// The raw-SDK-event -> stage mapping (spec §Implementation: "mapped from raw SDK events
// to a small set of human-readable stages"). `mapMessage` is a PURE function of one SDK
// message, so it is unit-testable without the SDK. It returns { stage, detail? } for a
// message that signals a new stage, or null for the vast majority of noise.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mapMessage } from '../../api/_lib/sdk-runner.js';
import { STAGES } from '../../api/_lib/handler.js';

test('a task_started for a venue subagent maps to researching_venues', () => {
  const m = mapMessage({
    type: 'system',
    subtype: 'task_started',
    subagent_type: 'research-venue',
    description: 'Find venues in Boise',
  });
  assert.equal(m.stage, 'researching_venues');
});

test('sponsor / talent research subagents map to their stages', () => {
  assert.equal(
    mapMessage({ type: 'system', subtype: 'task_started', description: 'sponsor prospecting' }).stage,
    'researching_sponsors',
  );
  assert.equal(
    mapMessage({ type: 'system', subtype: 'task_started', description: 'find mentors and judges' }).stage,
    'researching_talent',
  );
});

test('a verification task wins over the noun it mentions', () => {
  // "verify the venues" is a verification stage, not a venue-research stage.
  const m = mapMessage({ type: 'system', subtype: 'task_started', description: 'Verify the venue leads' });
  assert.equal(m.stage, 'verifying');
});

test('a Skill tool_use in an assistant message maps by skill name', () => {
  const m = mapMessage({
    type: 'assistant',
    message: {
      content: [
        { type: 'text', text: 'Let me build the schedule.' },
        { type: 'tool_use', name: 'Skill', input: { command: 'timeline' } },
      ],
    },
  });
  assert.equal(m.stage, 'building_timeline');
});

test('a Task tool_use maps by subagent_type', () => {
  const m = mapMessage({
    type: 'assistant',
    message: { content: [{ type: 'tool_use', name: 'Task', input: { subagent_type: 'plan-assembly' } }] },
  });
  assert.equal(m.stage, 'assembling');
});

test('intake / clarifier maps to intake', () => {
  assert.equal(
    mapMessage({ type: 'system', subtype: 'task_started', description: 'intake clarifier' }).stage,
    'intake',
  );
});

test('unrelated messages map to null (noise is dropped)', () => {
  assert.equal(mapMessage({ type: 'assistant', message: { content: [{ type: 'text', text: 'hi' }] } }), null);
  assert.equal(mapMessage({ type: 'system', subtype: 'thinking_tokens' }), null);
  assert.equal(mapMessage({ type: 'result', subtype: 'success', result: 'done' }), null);
  assert.equal(mapMessage(null), null);
  assert.equal(mapMessage('nonsense'), null);
});

test('every stage mapMessage can emit is a member of STAGES', () => {
  const samples = [
    { type: 'system', subtype: 'task_started', description: 'intake' },
    { type: 'system', subtype: 'task_started', description: 'venue search' },
    { type: 'system', subtype: 'task_started', description: 'sponsor search' },
    { type: 'system', subtype: 'task_started', description: 'mentor search' },
    { type: 'system', subtype: 'task_started', description: 'verify leads' },
    { type: 'system', subtype: 'task_started', description: 'timeline' },
    { type: 'system', subtype: 'task_started', description: 'assemble the plan' },
  ];
  for (const s of samples) {
    const m = mapMessage(s);
    assert.ok(m && STAGES.includes(m.stage), `unexpected stage for ${s.description}: ${m && m.stage}`);
  }
});
