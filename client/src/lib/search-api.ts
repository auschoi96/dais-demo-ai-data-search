import type { AgentKind, AgentRunState, StreamEvent } from '../../../shared/search-types';

export function emptyRun(agent: AgentKind): AgentRunState {
  return {
    agent,
    status: 'idle',
    tool_calls: [],
    text: '',
    tokens: 0,
    cost_usd: 0,
    latency_ms: 0,
    started_at: 0,
  };
}

function applyEvent(state: AgentRunState, evt: StreamEvent): AgentRunState {
  if (evt.agent !== state.agent) return state;
  switch (evt.type) {
    case 'session_start':
      return { ...state, status: 'running', started_at: Date.now() };
    case 'text_delta':
      return { ...state, text: state.text + evt.text };
    case 'tool_call':
      return {
        ...state,
        tool_calls: [
          ...state.tool_calls,
          {
            call_id: evt.call_id,
            name: evt.tool,
            args: evt.args,
            started_at: Date.now(),
          },
        ],
      };
    case 'tool_result': {
      const idx = state.tool_calls.findIndex((c) => c.call_id === evt.call_id);
      if (idx < 0) return state;
      const next = state.tool_calls.slice();
      next[idx] = { ...next[idx], output: evt.output, is_error: evt.is_error };
      return { ...state, tool_calls: next };
    }
    case 'done':
      return {
        ...state,
        status: 'ok',
        tokens: evt.tokens,
        cost_usd: evt.cost_usd,
        latency_ms: evt.latency_ms,
        finished_at: Date.now(),
      };
    case 'error':
      return {
        ...state,
        status: 'error',
        error: evt.message,
        latency_ms: evt.latency_ms ?? state.latency_ms,
        finished_at: Date.now(),
      };
  }
  return state;
}

export type RunsState = Record<AgentKind, AgentRunState>;

export function emptyRuns(): RunsState {
  return { vibe: emptyRun('vibe'), ready: emptyRun('ready') };
}

export function reduceRuns(state: RunsState, evt: StreamEvent): RunsState {
  return { ...state, [evt.agent]: applyEvent(state[evt.agent], evt) };
}

export type ModelChoice = 'opus' | 'sonnet' | 'haiku';

export const MODEL_OPTIONS: { value: ModelChoice; label: string; detail: string }[] = [
  { value: 'opus', label: 'Opus 5', detail: 'databricks-claude-opus-5 — most capable' },
  { value: 'sonnet', label: 'Sonnet 5', detail: 'databricks-claude-sonnet-5 — balanced' },
  { value: 'haiku', label: 'Haiku 4.5', detail: 'databricks-claude-haiku-4-5 — fastest' },
];

/** Open an SSE stream and feed each event to onEvent. Returns an abort fn. */
export async function streamAgents(
  query: string,
  model: ModelChoice,
  onEvent: (evt: StreamEvent) => void,
  onDone: () => void,
): Promise<() => void> {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch('/api/agents/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, model }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        onEvent({ type: 'error', agent: 'vibe', message: `HTTP ${response.status}` });
        onEvent({ type: 'error', agent: 'ready', message: `HTTP ${response.status}` });
        onDone();
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        // Normalize CRLF → LF so frame splitting works regardless of server line endings.
        buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');

        // SSE frames separated by blank line.
        let idx = buf.indexOf('\n\n');
        while (idx >= 0) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          const data = frame
            .split('\n')
            .filter((l) => l.startsWith('data:'))
            .map((l) => l.slice(5).trim())
            .join('');
          if (data) {
            try {
              onEvent(JSON.parse(data) as StreamEvent);
            } catch {
              // ignore malformed frame
            }
          }
          idx = buf.indexOf('\n\n');
        }
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        const msg = err instanceof Error ? err.message : 'stream failed';
        onEvent({ type: 'error', agent: 'vibe', message: msg });
        onEvent({ type: 'error', agent: 'ready', message: msg });
      }
    } finally {
      onDone();
    }
  })();

  return () => controller.abort();
}

export const AGENT_META: Record<AgentKind, { label: string; blurb: string; tools: string[] }> = {
  vibe: {
    label: 'General Purpose Agent',
    blurb: 'an out of the box claude code agent with no enrichment',
    tools: ['execute_sql (raw SQL runner)'],
  },
  ready: {
    label: 'AI-Ready Agent',
    blurb: 'an enriched claude code agent powered by Data Intelligence',
    tools: [
      'search_yape_services_enriched (VS)',
      'list_services_by_category',
      'top_services_by_region (metric view)',
      'compare_regions_adoption (metric view)',
      'avg_ticket_by_cohort (metric view)',
      'services_for_segment (metric view)',
      'query_metric_view (cross-cut introspector)',
      'execute_sql (fallback only)',
    ],
  },
};

export const HERO_QUERIES = [
  'What is the average ticket size for Yape Loans by age cohort?',
  'How much do users in Lima typically pay for streaming subscriptions?',
  '¿Qué servicios usan los usuarios para pagar el alquiler?',
  'Top services for sending plata in Cusco this quarter',
  'Compare savings adoption in Lima vs Trujillo',
  'Which insurance product has the highest average ticket?',
] as const;
