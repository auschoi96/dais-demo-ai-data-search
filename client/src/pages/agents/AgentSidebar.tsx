import { Badge } from '@databricks/appkit-ui/react';
import { AGENT_META } from '../../lib/search-api';
import type { AgentKind, AgentRunState } from '../../../../shared/search-types';
import type { RunsState } from '../../lib/search-api';

const AGENTS: AgentKind[] = ['vibe', 'ready'];

export function AgentSidebar({ runs, now }: { runs: RunsState; now: number }) {
  const hasAny = AGENTS.some((k) => runs[k].status !== 'idle');
  const done = AGENTS.every((k) => runs[k].status === 'ok' || runs[k].status === 'error');

  return (
    <aside className="w-80 shrink-0 border-l bg-muted/30 flex flex-col">
      <div className="px-4 py-3 border-b bg-card flex items-center gap-2">
        <h2 className="font-semibold text-foreground">Comparison</h2>
        {hasAny && (
          <Badge variant="secondary" className="ml-auto">
            {AGENTS.filter((k) => runs[k].status === 'ok' || runs[k].status === 'error').length}/2
          </Badge>
        )}
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-3">
        {!hasAny ? (
          <EmptyState />
        ) : (
          <>
            {AGENTS.map((k) => (
              <RunCard key={k} run={runs[k]} now={now} />
            ))}
            {done && <DeltaSummary runs={runs} />}
          </>
        )}
      </div>
    </aside>
  );
}

function EmptyState() {
  return (
    <div className="text-center text-sm text-muted-foreground mt-12">
      <ScaleIcon />
      <p className="mt-3">No runs yet.</p>
      <p className="text-xs">
        Send a query — both agents run in parallel and stream their tool calls.
      </p>
    </div>
  );
}

function RunCard({ run, now }: { run: AgentRunState; now: number }) {
  const meta = AGENT_META[run.agent];
  const isReady = run.agent === 'ready';
  const elapsedMs =
    run.status === 'ok' || run.status === 'error'
      ? run.latency_ms
      : run.started_at
        ? now - run.started_at
        : 0;

  return (
    <div className="bg-card border rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              isReady ? 'bg-success' : 'bg-warning'
            } ${run.status === 'running' ? 'animate-pulse' : ''}`}
          />
          <span className="text-xs font-medium text-foreground">{meta.label}</span>
        </div>
        <StatusDot status={run.status} />
      </div>

      <div className="space-y-1 text-xs">
        <Stat label="Wall time" value={`${(elapsedMs / 1000).toFixed(1)}s`} mono />
        <Stat label="Tool calls" value={String(run.tool_calls.length)} mono />
        <Stat
          label="Tokens"
          value={run.tokens > 0 ? run.tokens.toLocaleString() : run.status === 'running' ? '…' : '—'}
          mono
        />
        {run.cost_usd > 0 && <Stat label="Cost" value={`$${run.cost_usd.toFixed(4)}`} mono />}
      </div>

      {run.status === 'error' && run.error && (
        <div className="text-xs text-destructive break-words">{run.error}</div>
      )}
    </div>
  );
}

function DeltaSummary({ runs }: { runs: RunsState }) {
  const vibe = runs.vibe;
  const ready = runs.ready;
  const slower = vibe.latency_ms / Math.max(ready.latency_ms, 1);
  const tokenRatio = vibe.tokens / Math.max(ready.tokens, 1);
  const extraCalls = vibe.tool_calls.length - ready.tool_calls.length;

  return (
    <div className="bg-primary/5 border border-primary/30 rounded-lg p-3 space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wider text-primary">
        AI-ready delta
      </div>
      <div className="text-xs text-foreground space-y-1">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Vibe was slower by</span>
          <span className="font-mono tabular-nums">{slower.toFixed(1)}x</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Vibe burned tokens</span>
          <span className="font-mono tabular-nums">{tokenRatio.toFixed(1)}x</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Extra tool calls</span>
          <span className="font-mono tabular-nums">+{extraCalls}</span>
        </div>
      </div>
      <div className="text-[10px] text-muted-foreground italic pt-1 border-t">
        Same model, same prompt. The vibe agent had to figure out the schema,
        iterate on broken queries, and string results together. AI-ready agent called
        one metric view.
      </div>
    </div>
  );
}

function Stat({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between items-baseline gap-2">
      <span className="text-muted-foreground">{label}:</span>
      <span className={`text-foreground tabular-nums ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  );
}

function StatusDot({ status }: { status: AgentRunState['status'] }) {
  const colors: Record<AgentRunState['status'], string> = {
    idle: 'bg-muted',
    running: 'bg-warning animate-pulse',
    ok: 'bg-success',
    error: 'bg-destructive',
  };
  return <span className={`w-2 h-2 rounded-full ${colors[status]}`} />;
}

function ScaleIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto opacity-40">
      <path d="M12 3v18M6 9h12M3 13a3 3 0 0 0 6 0L6 5l-3 8zM15 13a3 3 0 0 0 6 0L18 5l-3 8z" />
    </svg>
  );
}
