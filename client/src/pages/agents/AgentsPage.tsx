import { useEffect, useRef, useState } from 'react';
import {
  Button,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
} from '@databricks/appkit-ui/react';
import { AgentColumn } from './AgentColumn';
import { AgentSidebar } from './AgentSidebar';
import {
  AGENT_META,
  HERO_QUERIES,
  MODEL_OPTIONS,
  emptyRuns,
  reduceRuns,
  streamAgents,
  type ModelChoice,
  type RunsState,
} from '../../lib/search-api';
import type { AgentKind } from '../../../../shared/search-types';

const AGENTS: AgentKind[] = ['vibe', 'ready'];

export function AgentsPage() {
  const [query, setQuery] = useState<string>(HERO_QUERIES[0]);
  const [model, setModel] = useState<ModelChoice>('opus');
  const [runs, setRuns] = useState<RunsState>(emptyRuns());
  const [running, setRunning] = useState(false);
  const [now, setNow] = useState(Date.now());
  const abortRef = useRef<(() => void) | null>(null);

  // Ticking clock for live elapsed counters
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [running]);

  async function handleSubmit() {
    const trimmed = query.trim();
    if (!trimmed || running) return;
    setRunning(true);
    setRuns({
      vibe: { ...emptyRuns().vibe, status: 'running', started_at: Date.now() },
      ready: { ...emptyRuns().ready, status: 'running', started_at: Date.now() },
    });
    abortRef.current = await streamAgents(
      trimmed,
      model,
      (evt) => setRuns((curr) => reduceRuns(curr, evt)),
      () => setRunning(false),
    );
  }

  function handleCancel() {
    abortRef.current?.();
    setRunning(false);
  }

  const hasRun = runs.vibe.status !== 'idle' || runs.ready.status !== 'idle';

  return (
    <div className="flex h-full">
      <main className="flex-1 flex flex-col min-w-0">
        <div className="px-6 py-4 border-b flex items-start gap-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold text-foreground">Two agents, same query.</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              The General purpose agent is not powered by Data Intelligence. Watch as the
              AI-Ready Agent is able to use Data Intelligence to reduce tool-call count, wall
              time and token usage.
            </p>
          </div>
          <div className="shrink-0 min-w-[180px]">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground block mb-1">
              Model
            </label>
            <Select value={model} onValueChange={(v) => setModel(v as ModelChoice)} disabled={running}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Pick a model" />
              </SelectTrigger>
              <SelectContent>
                {MODEL_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    <div className="flex flex-col">
                      <span className="font-medium">{opt.label}</span>
                      <span className="text-[10px] text-muted-foreground">{opt.detail}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-6">
          {!hasRun ? (
            <EmptyState />
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-full">
              {AGENTS.map((k) => (
                <AgentColumn key={k} run={runs[k]} now={now} />
              ))}
            </div>
          )}
        </div>

        <div className="border-t px-6 py-4 bg-card">
          <div className="flex flex-wrap gap-2 mb-3">
            {HERO_QUERIES.map((hero) => (
              <button
                key={hero}
                type="button"
                onClick={() => setQuery(hero)}
                className="text-sm px-3 py-1.5 rounded-md bg-muted text-foreground hover:bg-accent transition-colors text-left"
              >
                {hero}
              </button>
            ))}
          </div>
          <div className="flex items-end gap-3">
            <Textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder="Ask both agents the same question…"
              className="flex-1 min-h-[56px] resize-none"
              rows={2}
            />
            {running ? (
              <Button
                onClick={handleCancel}
                variant="outline"
                className="rounded-full w-12 h-12 p-0 shrink-0"
                aria-label="Cancel"
              >
                <StopIcon />
              </Button>
            ) : (
              <Button
                onClick={handleSubmit}
                disabled={!query.trim()}
                className="rounded-full w-12 h-12 p-0 shrink-0"
                aria-label="Run both agents"
              >
                <ArrowRight />
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            ⌘/Ctrl + Enter to send · streams tool calls live as each agent works
          </p>
        </div>
      </main>

      <AgentSidebar runs={runs} now={now} />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="max-w-3xl mx-auto mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
      {(['vibe', 'ready'] as AgentKind[]).map((a) => {
        const meta = AGENT_META[a];
        return (
          <div key={a} className="border rounded-lg p-4 bg-card">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`w-2 h-2 rounded-full ${a === 'ready' ? 'bg-success' : 'bg-warning'}`}
              />
              <h3 className="font-semibold text-foreground">{meta.label}</h3>
            </div>
            <p className="text-sm text-muted-foreground mb-3">{meta.blurb}</p>
            <div className="text-xs text-muted-foreground space-y-1">
              <div className="font-medium uppercase tracking-wider mb-1">Tools</div>
              {meta.tools.map((t) => (
                <div key={t} className="font-mono text-[11px]">
                  · {t}
                </div>
              ))}
            </div>
          </div>
        );
      })}
      <div className="md:col-span-2 text-center text-sm text-muted-foreground mt-2">
        Pick a query and watch each agent stream its tool calls in real time. Same model,
        same prompt scaffolding — the data layer is the variable.
      </div>
    </div>
  );
}

function ArrowRight() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}
