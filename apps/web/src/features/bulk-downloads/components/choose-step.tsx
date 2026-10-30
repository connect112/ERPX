import { ChevronLeft, ChevronRight, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type BulkSource, type SourceInfo, useBulkItems } from "@/features/bulk-downloads/api/bulk-downloads-api";
import {
  type Selection,
  count,
  emptySelection,
  isSelected,
  pageState,
  selectAllMatching,
  setPage,
  toggle,
} from "@/features/bulk-downloads/lib/selection";

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";
export const PAGE_SIZE = 25;

export interface ChooseFilters {
  search: string;
  status: string;
  page: number;
}

interface Props {
  source: BulkSource;
  scopeId: string | null;
  info: SourceInfo;
  filters: ChooseFilters;
  onFilters: (f: ChooseFilters) => void;
  selection: Selection;
  onSelection: (s: Selection) => void;
}

export function ChooseStep({ source, scopeId, info, filters, onFilters, selection, onSelection }: Props) {
  const { data, isLoading, isError } = useBulkItems(
    source,
    scopeId,
    { search: filters.search, status: filters.status, page: filters.page, pageSize: PAGE_SIZE },
    true
  );
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pageIds = items.map((i) => i.id);
  const state = pageState(selection, pageIds);
  const chosen = count(selection, total);
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const statusLabel = new Map(info.status_options.map((o) => [o.value, o.label]));

  // "All matching" is tied to the filters on screen, so changing them starts the choice again.
  const changeFilters = (next: Partial<ChooseFilters>) => {
    if (selection.mode === "all") onSelection(emptySelection());
    onFilters({ ...filters, page: 1, ...next });
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            aria-label="Search"
            className="pl-8"
            placeholder="Search by name, email or ID"
            value={filters.search}
            onChange={(e) => changeFilters({ search: e.target.value })}
          />
        </div>
        {info.status_options.length > 0 && (
          <select
            aria-label="Status"
            className={selectClass}
            value={filters.status}
            onChange={(e) => changeFilters({ status: e.target.value })}
          >
            <option value="">All</option>
            {info.status_options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        )}
      </div>

      {state === "all" && selection.mode === "some" && total > items.length && (
        <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm dark:border-blue-500/30 dark:bg-blue-500/10">
          All {items.length} on this page are chosen.{" "}
          <button type="button" className="font-medium underline" onClick={() => onSelection(selectAllMatching())}>
            Choose all {total} that match
          </button>
        </div>
      )}
      {selection.mode === "all" && (
        <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm dark:border-blue-500/30 dark:bg-blue-500/10">
          All {total} matching documents are chosen
          {selection.excluded.size > 0 && `, except ${selection.excluded.size} you unticked`}.{" "}
          <button type="button" className="font-medium underline" onClick={() => onSelection(emptySelection())}>
            Clear
          </button>
        </div>
      )}

      <div className="max-h-[45vh] overflow-y-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <input
                  type="checkbox"
                  aria-label="Choose every document on this page"
                  disabled={items.length === 0}
                  checked={state === "all"}
                  ref={(el) => {
                    if (el) el.indeterminate = state === "some";
                  }}
                  onChange={(e) => onSelection(setPage(selection, pageIds, e.target.checked))}
                />
              </TableHead>
              <TableHead>Document</TableHead>
              <TableHead>Details</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>
                  <input
                    type="checkbox"
                    aria-label={`Choose ${item.title}`}
                    checked={isSelected(selection, item.id)}
                    onChange={() => onSelection(toggle(selection, item.id))}
                  />
                </TableCell>
                <TableCell className="font-medium">{item.title}</TableCell>
                <TableCell className="text-muted-foreground">{item.subtitle}</TableCell>
                <TableCell>
                  {item.status && <Badge variant="secondary">{statusLabel.get(item.status) ?? item.status}</Badge>}
                </TableCell>
              </TableRow>
            ))}
            {!isLoading && items.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="py-8 text-center text-muted-foreground">
                  {isError ? "The documents could not be loaded." : "No documents match."}
                </TableCell>
              </TableRow>
            )}
            {isLoading && (
              <TableRow>
                <TableCell colSpan={4} className="py-8 text-center text-muted-foreground">
                  Loading…
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-muted-foreground">
          <strong className="text-foreground">{chosen}</strong> chosen of {total}
          {chosen > info.max_items && <span className="text-destructive"> (at most {info.max_items} per download)</span>}
        </span>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            aria-label="Previous page"
            disabled={filters.page <= 1}
            onClick={() => onFilters({ ...filters, page: filters.page - 1 })}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span>
            Page {filters.page} of {pages}
          </span>
          <Button
            size="sm"
            variant="outline"
            aria-label="Next page"
            disabled={filters.page >= pages}
            onClick={() => onFilters({ ...filters, page: filters.page + 1 })}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
