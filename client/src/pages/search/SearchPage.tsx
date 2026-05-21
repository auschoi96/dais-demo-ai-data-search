import { useState } from 'react';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
  Textarea,
} from '@databricks/appkit-ui/react';
import { TierPicker } from './TierPicker';
import { RunDetailsSidebar } from './RunDetailsSidebar';
import { TierResultColumn } from './TierResultColumn';
import {
  HERO_QUERIES,
  TIER_LABELS,
  runTiers,
  type TierRun,
} from '../../lib/search-api';
import type { SearchTier } from '../../../../shared/search-types';

const ALL_TIERS: SearchTier[] = ['0', '1', '2', '3'];
const DEFAULT_TIERS: SearchTier[] = ['0', '2'];

export function SearchPage() {
  const [query, setQuery] = useState('I want to save money');
  const [selectedTiers, setSelectedTiers] = useState<SearchTier[]>(DEFAULT_TIERS);
  const [runs, setRuns] = useState<Record<SearchTier, TierRun>>({} as Record<SearchTier, TierRun>);
  const [running, setRunning] = useState(false);

  function toggleTier(tier: SearchTier, on: boolean) {
    setSelectedTiers((curr) => {
      if (on && !curr.includes(tier)) return [...curr, tier].sort();
      if (!on) return curr.filter((t) => t !== tier);
      return curr;
    });
  }

  function setAll(on: boolean) {
    setSelectedTiers(on ? [...ALL_TIERS] : []);
  }

  async function handleSubmit() {
    const trimmed = query.trim();
    if (!trimmed || selectedTiers.length === 0 || running) return;
    setRunning(true);
    const initial: Record<SearchTier, TierRun> = {} as Record<SearchTier, TierRun>;
    for (const t of selectedTiers) initial[t] = { tier: t, status: 'pending' };
    setRuns(initial);

    await runTiers(trimmed, selectedTiers, (run) => {
      setRuns((curr) => ({ ...curr, [run.tier]: run }));
    });
    setRunning(false);
  }

  const hasRun = Object.values(runs).length > 0;
  const orderedRuns = selectedTiers.map((t) => runs[t]).filter(Boolean);

  return (
    <div className="flex h-full">
      <main className="flex-1 flex flex-col min-w-0">
        <div className="px-6 py-4 border-b flex items-center justify-between gap-4">
          <div>
            <h1 className="text-lg font-bold text-foreground">Yape Service Search</h1>
            <p className="text-sm text-muted-foreground">
              Compare search tiers side-by-side. Pick which ones to run, send a query.
            </p>
          </div>
          <TierPicker
            selected={selectedTiers}
            onToggle={toggleTier}
            onSetAll={setAll}
          />
        </div>

        <div className="flex-1 overflow-auto px-6 py-6">
          {!hasRun && (
            <EmptyState
              query={query}
              setQuery={setQuery}
              selectedTiers={selectedTiers}
            />
          )}

          {hasRun && (
            <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${orderedRuns.length}, minmax(260px, 1fr))` }}>
              {orderedRuns.map((run) => (
                <TierResultColumn key={run.tier} run={run} />
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
                className="text-sm px-3 py-1.5 rounded-md bg-muted text-foreground hover:bg-accent transition-colors"
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
              placeholder="Ask Yape… e.g. quiero ahorrar"
              className="flex-1 min-h-[56px] resize-none"
              rows={2}
            />
            <Button
              onClick={handleSubmit}
              disabled={running || !query.trim() || selectedTiers.length === 0}
              className="rounded-full w-12 h-12 p-0 shrink-0"
              aria-label="Run search"
            >
              {running ? <Spinner /> : <ArrowRight />}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            ⌘/Ctrl + Enter to send · {selectedTiers.length} of 4 tiers selected
          </p>
        </div>
      </main>

      <RunDetailsSidebar runs={orderedRuns} />
    </div>
  );
}

function EmptyState({
  query,
  setQuery,
  selectedTiers,
}: {
  query: string;
  setQuery: (v: string) => void;
  selectedTiers: SearchTier[];
}) {
  return (
    <div className="max-w-2xl mx-auto mt-12 text-center space-y-6">
      <div>
        <h2 className="text-3xl font-bold text-foreground mb-2">
          Same query, different data.
        </h2>
        <p className="text-muted-foreground">
          Pick tiers above and send a query. T0/T1 fail on intent phrasing — T2 succeeds
          because the data is semantic, governed, and vectorized.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {selectedTiers.map((t) => (
          <Card key={t}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Badge variant="outline">T{t}</Badge>
                {TIER_LABELS[t]}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Skeleton className="h-3 w-full mb-2" />
              <Skeleton className="h-3 w-3/4" />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-wrap justify-center gap-2 pt-2">
        {HERO_QUERIES.slice(0, 3).map((hero) => (
          <button
            key={hero}
            type="button"
            onClick={() => setQuery(hero)}
            className={`text-sm px-3 py-1.5 rounded-md border transition-colors ${
              query === hero ? 'border-primary text-primary' : 'border-border hover:bg-muted'
            }`}
          >
            {hero}
          </button>
        ))}
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

function Spinner() {
  return (
    <svg className="animate-spin" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}
