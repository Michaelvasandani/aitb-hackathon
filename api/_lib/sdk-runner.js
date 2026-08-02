// The ONLY place the Claude Agent SDK is invoked (ADR-0001). Everything paid and
// non-deterministic lives behind the `runPlan(inputs, emit)` boundary so the handler and
// its test seam never touch the SDK.
//
// (settingSources: ['project']), runs the pipeline (orchestrator -> intake -> research
// fan-out -> timeline -> plan-assembly), maps the noisy message stream down
// to the small STAGES set via `emit`, and returns the assembled { id, plan_json, plan_html } —
// the plan read back from the files plan-assembly wrote, plus the per-run UUID for the
// permalink (ADR-0003). The SDK seam mints the id but never touches the database.

import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';

const HERE = path.dirname(fileURLToPath(import.meta.url)); // api/_lib
export const REPO_ROOT = path.resolve(HERE, '..', '..'); // where .claude/skills lives

// Sonnet 5: capable enough to drive the full multi-skill orchestration to completion (Haiku
// 4.5 finished early without ever writing plan.json). The original timeout is addressed by the
// 800s ceiling (Vercel Pro) + the 3-lead caps, so Sonnet now has time AND less work. Escalate
// to 'claude-opus-4-8' only if lead quality disappoints.
export const DEFAULT_MODEL = 'claude-sonnet-5';

// ---- pure event mapping -------------------------------------------------------------

// Ordered longest-intent-first: a "verify the venues" task is verification, not venue
// research, so `verif` must be tested before `venue`.
// NOTE: the dedicated verification pass is currently disabled (see
// docs/decisions/0001-disable-verification-stage.md), so the 'verifying' stage is inert
// plumbing — kept so the STAGES contract and restore path stay intact; it just won't fire.
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
    '   Keep each list SHORT — EXACTLY 3 well-sourced leads per category (the skills cap at 3).',
    '   (The separate adversarial verification pass is DISABLED for now — it was the run-time',
    '   bottleneck; see docs/decisions/0001-disable-verification-stage.md. Sourced-or-omitted',
    '   still holds: only include a lead if you have a real source_url for it.)',
    '3. Build the timeline counting back from the event window (timeline).',
    '4. Assemble the final plan (plan-assembly) as ONE self-contained HTML file.',
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

  // Diagnostics: the SDK's terminal `result` message tells us how the run ended (success,
  // max_turns, error). We log a summary so a failed run is explainable from Vercel logs
  // instead of a generic error. Never logs env / the API key.
  let msgCount = 0;
  let result = null;
  let lastAssistantText = '';
  try {
    for await (const msg of response) {
      msgCount += 1;
      if (msg && msg.type === 'result') result = msg;
      if (msg && msg.type === 'assistant' && msg.message && Array.isArray(msg.message.content)) {
        const text = msg.message.content.filter((b) => b && b.type === 'text').map((b) => b.text).join(' ');
        if (text) lastAssistantText = text;
      }
      const mapped = mapMessage(msg);
      if (mapped && mapped.stage !== lastStage) {
        lastStage = mapped.stage;
        emit(mapped);
      }
    }
  } finally {
    abortController.abort();
  }

  const summary = {
    messages: msgCount,
    result_subtype: result ? result.subtype : null,
    is_error: result ? result.is_error : null,
    num_turns: result ? result.num_turns : null,
    last_stage: lastStage,
    last_assistant_text: lastAssistantText.slice(0, 400),
  };
  console.log('[runPlan] run finished', JSON.stringify(summary));

  // The deliverable is whatever plan-assembly wrote. If it is absent or unparseable, the
  // run did not produce a plan — surface that as a failure (handler -> error event).
  let plan_json;
  try {
    plan_json = JSON.parse(await fs.readFile(jsonPath, 'utf8'));
  } catch (err) {
    let tmpListing = [];
    try {
      tmpListing = (await fs.readdir(os.tmpdir())).filter((f) => f.startsWith('plan-'));
    } catch { /* ignore */ }
    console.error('[runPlan] no valid plan.json at', jsonPath, JSON.stringify({
      read_error: String(err && err.message || err),
      tmp_plan_files: tmpListing,
      ...summary,
    }));
    throw new Error('Pipeline finished without writing a valid plan.json');
  }
  let plan_html;
  try {
    plan_html = await fs.readFile(htmlPath, 'utf8');
  } catch {
    console.error('[runPlan] plan.json present but plan.html missing at', htmlPath);
    throw new Error('Pipeline finished without writing plan.html');
  }

  // Surface the per-run UUID as `id` so the handler can persist and permalink the run
  // (ADR-0003). The SDK seam mints the id but never touches the database — persistence is
  // the handler's job, through the store seam.
  return { id: runId, plan_json, plan_html };
}
