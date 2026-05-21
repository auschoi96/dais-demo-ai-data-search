import {
  Button,
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@databricks/appkit-ui/react';
import { TIER_LABELS, TIER_BLURB } from '../../lib/search-api';
import type { SearchTier } from '../../../../shared/search-types';

const ALL: SearchTier[] = ['0', '1', '2', '3'];

export function TierPicker({
  selected,
  onToggle,
  onSetAll,
}: {
  selected: SearchTier[];
  onToggle: (tier: SearchTier, on: boolean) => void;
  onSetAll: (on: boolean) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="font-medium">
          Tiers: {selected.length}/4
          <ChevronDown />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-wider text-muted-foreground">
            Available tiers
          </span>
          <div className="flex gap-2 text-xs">
            <button
              type="button"
              onClick={() => onSetAll(true)}
              className="text-primary hover:underline"
            >
              All
            </button>
            <button
              type="button"
              onClick={() => onSetAll(false)}
              className="text-primary hover:underline"
            >
              None
            </button>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {ALL.map((t) => (
          <DropdownMenuCheckboxItem
            key={t}
            checked={selected.includes(t)}
            onCheckedChange={(v) => onToggle(t, Boolean(v))}
            onSelect={(e) => e.preventDefault()}
            className="py-2"
          >
            <div className="flex flex-col gap-0.5">
              <div className="font-medium text-sm">T{t} — {TIER_LABELS[t]}</div>
              <div className="text-xs text-muted-foreground">{TIER_BLURB[t]}</div>
            </div>
          </DropdownMenuCheckboxItem>
        ))}
        <DropdownMenuSeparator />
        <div className="px-2 py-1.5 text-xs text-muted-foreground">
          Applies to the next query you send.
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ChevronDown() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="ml-1">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
