// The ONLY place the Claude Agent SDK is invoked (ADR-0001). Everything paid and
// non-deterministic lives behind the `runPlan(inputs, emit)` boundary so the handler and
// its test seam never touch the SDK.
//
// runPlan drives the JS `@anthropic-ai/claude-agent-sdk` against the repo's `.claude/skills/`
// (settingSources: ['project']), runs the full pipeline (orchestrator -> intake -> research
// fan-out -> verification -> timeline -> plan-assembly), maps the noisy message stream down
// to the small STAGES set via `emit`, and returns the assembled { plan_json, plan_html } read
// back from the files the plan-assembly skill wrote.

import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';

const HERE = path.dirname(fileURLToPath(import.meta.url)); // api/_lib
export const REPO_ROOT = path.resolve(HERE, '..', '..'); // where .claude/skills lives

// Sonnet 5: fast + cheap for a token-heavy research run (ADR-0001). Escalate to Opus only
// if lead quality disappoints.
export const DEFAULT_MODEL = 'claude-sonnet-5';

// ---- pure event mapping -------------------------------------------------------------

// Ordered longest-intent-first: a "verify the venues" task is verification, not venue
// research, so `verif` must be tested before `venue`.
const STAGE_PATTERNS = [
  [/\bverif/, 'verifying'],
  [/\bintake\b|clarif/, 'intake'],
  [/venue/, 'researching_venues'],
  [/sponsor/, 'researching_sponsors'],
  [/talent|mentor|judge/, 'researching_talent'],
  [/timeline|run.?of.?show|counting back/, 'building_timeline'],
  [/assembl|plan-assembly|render/, 'assembling'],
];

function stageFromText(text) {
  if (!text) return null;
  const t = String(text).toLowerCase();
  for (const [re, stage] of STAGE_PATTERNS) {
    if (re.test(t)) return stage;
  }
  return null;
}

// Map ONE SDK message to a { stage, detail? } event, or null if it signals no new stage.
// Pure and stateless — the caller dedupes consecutive repeats.
export function mapMessage(msg) {
  if (!msg || typeof msg !== 'object') return null;

  // Strongest signal: a subagent task starting (the fan-out fingerprint).
  if (msg.type === 'system' && msg.subtype === 'task_started') {
    const stage = stageFromText([msg.subagent_type, msg.description, msg.prompt].filter(Boolean).join(' '));
    if (stage) return msg.description ? { stage, detail: msg.description } : { stage };
    return null;
  }

  // Next: a Skill or Task tool_use inside an assistant turn.
  if (msg.type === 'assistant' && msg.message && Array.isArray(msg.message.content)) {
    for (const block of msg.message.content) {
      if (!block || block.type !== 'tool_use') continue;
      const input = block.input || {};
      if (block.name === 'Skill') {
        const stage = stageFromText([input.command, input.name, input.skill].filter(Boolean).join(' '));
        if (stage) return { stage };
      } else if (block.name === 'Task') {
        const stage = stageFromText([input.subagent_type, input.description, input.prompt].filter(Boolean).join(' '));
        if (stage) return { stage };
      }
    }
  }

  return null;
}

// ---- the real SDK run ---------------------------------------------------------------

function buildPrompt(inputs, jsonPath, htmlPath) {
  return [
    'You are running the Hack-AI-Thon-in-a-Box agentic pipeline headless. Use the project',
    'skills (orchestrator, intake-clarifier, research-venue, research-sponsor,',
    'research-talent, timeline, plan-assembly) and the shared data contract.',
    '',
    'Plan a hackathon for this organizer. Raw inputs (JSON):',
    JSON.stringify(inputs, null, 2),
    '',
    'Run the FULL pipeline:',
    '1. Normalize the inputs (intake-clarifier) into the data-contract `inputs` object.',
    '2. Research venues, sponsors, and talent for the city. Dispatch research-venue,',
    '   research-sponsor, and research-talent as PARALLEL subagents (one Task tool call per',
    '   specialist, sent together) so they run concurrently. Use web search for every lead.',
    '   Every lead MUST carry a real, working `source_url`; OMIT any lead you cannot source.',
    '   Keep each list SHORT — aim for 3-5 well-sourced leads per category to stay fast.',
    '3. Run the adversarial verification pass on the leads (drop/downgrade confidence).',
    '4. Build the timeline counting back from the event window (timeline).',
    '5. Assemble the final plan (plan-assembly) as ONE self-contained HTML file.',
    '',
    'Write outputs to EXACTLY these paths (do not choose your own):',
    `- structured plan (plan.json): ${jsonPath}`,
    `- self-contained plan (plan.html): ${htmlPath}`,
    '',
    'plan.json MUST have these top-level keys: inputs, timeline, run_of_show, leads,',
    'templates, warnings, meta. plan.html MUST be fully self-contained (inline CSS, no',
    'external requests). When BOTH files are written, reply with the single word DONE.',
  ].join('\n');
}

export async function runPlan(inputs, emit) {
  // Import lazily so the handler module (and its tests) never load the SDK.
  const { query } = await import('@anthropic-ai/claude-agent-sdk');

  const runId = randomUUID();
  const jsonPath = path.join(os.tmpdir(), `plan-${runId}.json`);
  const htmlPath = path.join(os.tmpdir(), `plan-${runId}.html`);

  emit({ stage: 'intake' });
  let lastStage = 'intake';

  const abortController = new AbortController();
  const response = query({
    prompt: buildPrompt(inputs, jsonPath, htmlPath),
    options: {
      cwd: REPO_ROOT, // so .claude/skills + .claude/settings.json are discovered
      model: DEFAULT_MODEL,
      settingSources: ['project'],
      skills: 'all',
      permissionMode: 'bypassPermissions',
      allowDangerouslySkipPermissions: true,
      allowedTools: ['Read', 'Write', 'Edit', 'Bash', 'Grep', 'Glob', 'WebSearch', 'WebFetch', 'Task', 'Skill', 'TodoWrite'],
      maxTurns: 200,
      abortController,
      // Inherit env (incl. ANTHROPIC_API_KEY, PATH) for the subprocess. Never logged.
      env: { ...process.env },
    },
  });

  try {
    for await (const msg of response) {
      const mapped = mapMessage(msg);
      if (mapped && mapped.stage !== lastStage) {
        lastStage = mapped.stage;
        emit(mapped);
      }
    }
  } finally {
    abortController.abort();
  }

  // The deliverable is whatever plan-assembly wrote. If it is absent or unparseable, the
  // run did not produce a plan — surface that as a failure (handler -> error event).
  let plan_json;
  try {
    plan_json = JSON.parse(await fs.readFile(jsonPath, 'utf8'));
  } catch {
    throw new Error('Pipeline finished without writing a valid plan.json');
  }
  let plan_html;
  try {
    plan_html = await fs.readFile(htmlPath, 'utf8');
  } catch {
    throw new Error('Pipeline finished without writing plan.html');
  }

  return { plan_json, plan_html };
}
