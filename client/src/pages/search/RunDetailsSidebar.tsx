import { Badge } from '@databricks/appkit-ui/react';
import { TIER_LABELS } from '../../lib/search-api';
import type { TierRun } from '../../lib/search-api';

export function RunDetailsSidebar({ runs }: { runs: TierRun[] }) {
  const completed = runs.filter((r) => r.status === 'ok');

  return (
    <aside className="w-80 shrink-0 border-l bg-muted/30 flex flex-col">
      <div className="px-4 py-3 border-b bg-card flex items-center gap-2">
        <h2 className="font-semibold text-foreground">Run details</h2>
        {runs.length > 0 && (
          <Badge variant="secondary" className="ml-auto">
            {completed.length}/{runs.length}
          </Badge>
        )}
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-3">
        {runs.length === 0 && (
          <div className="text-center text-sm text-muted-foreground mt-12">
            <SearchIcon />
            <p className="mt-3">No runs yet.</p>
            <p className="text-xs">Send a query to see per-tier latency, scores, and traces.</p>
          </div>
        )}

        {runs.map((run) => (
          <RunCard key={run.tier} run={run} />
        ))}
      </div>
    </aside>
  );
}

function RunCard({ run }: { run: TierRun }) {
  const top = run.response?.results[0];
  return (
    <div className="bg-card border rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant={run.tier === '2' ? 'default' : 'outline'}>T{run.tier}</Badge>
          <span className="text-xs font-medium text-foreground">{TIER_LABELS[run.tier]}</span>
        </div>
        <StatusDot status={run.status} />
      </div>

      {run.status === 'pending' && (
        <div className="text-xs text-muted-foreground">Running…</div>
      )}

      {run.status === 'error' && (
        <div className="text-xs text-destructive break-words">{run.error}</div>
      )}

      {run.status === 'ok' && run.response && (
        <>
          <div className="flex gap-2 text-xs">
            <span className="font-mono text-muted-foreground">{run.response.latency_ms}ms</span>
            <span className="text-muted-foreground">·</span>
            <span className="text-muted-foreground">{run.response.results.length} hits</span>
          </div>

          {top ? (
            <div className="text-xs">
              <div className="text-muted-foreground mb-0.5">Top result:</div>
              <div className="font-medium text-foreground truncate">{top.icon ?? '🔎'} {top.name}</div>
              {top.score != null && (
                <div className="font-mono text-[10px] text-muted-foreground mt-0.5">
                  score {top.score.toFixed(3)}
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs italic text-muted-foreground">No matches</div>
          )}

          {run.response.trace_url && (
            <a
              href={run.response.trace_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-primary underline underline-offset-2 inline-flex items-center gap-1"
            >
              MLflow trace ↗
            </a>
          )}
        </>
      )}
    </div>
  );
}

function StatusDot({ status }: { status: TierRun['status'] }) {
  const colors = {
    pending: 'bg-warning animate-pulse',
    ok: 'bg-success',
    error: 'bg-destructive',
  };
  return <span className={`w-2 h-2 rounded-full ${colors[status]}`} />;
}

function SearchIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto opacity-40">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}
