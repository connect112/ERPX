import { ArrowDown, ArrowUp, ChevronRight, Folder, HardDrive, Lock, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { FileFilters, FileItem } from "@/features/storage-manager/api/storage-api";
import { useFiles } from "@/features/storage-manager/api/storage-hooks";
import { DeleteDialog } from "@/features/storage-manager/components/delete-dialog";
import { FileDetailsDialog } from "@/features/storage-manager/components/file-details-dialog";
import { StatusBadge } from "@/features/storage-manager/components/status-badge";
import { formatBytes, formatDate, pathLabel, STATUS_LABELS } from "@/features/storage-manager/lib/format";
import { hasActiveFilters, isDeletable, nextSort, totalBytes } from "@/features/storage-manager/lib/rules";

const PAGE_SIZE = 50;

const TYPE_OPTIONS = ["image", "pdf", "video", "audio", "text", "office", "archive", "database", "other"];

interface Props {
  canDelete: boolean;
  initialStatus?: string;
}

const SORTABLE: { key: string; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "source", label: "Source" },
  { key: "size", label: "Size" },
  { key: "date", label: "Created" },
  { key: "owner", label: "Owner" },
  { key: "status", label: "Status" },
];

const selectClass = "h-10 rounded-md border border-input bg-background px-3 text-sm";

export function FilesPanel({ canDelete, initialStatus }: Props) {
  const [filters, setFilters] = useState<FileFilters>({
    path: [],
    status: initialStatus,
    sort: "name",
    order: "asc",
    page: 1,
    page_size: PAGE_SIZE,
  });
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Map<string, FileItem>>(new Map());
  const [detail, setDetail] = useState<FileItem | null>(null);
  const [deleteIds, setDeleteIds] = useState<string[] | null>(null);

  const { data, isLoading, isError, isFetching } = useFiles(filters);

  const update = (patch: Partial<FileFilters>) => setFilters((current) => ({ ...current, page: 1, ...patch }));
  const sortBy = (key: string) => update({ ...nextSort(filters, key), page: filters.page });

  const items = useMemo(() => data?.items ?? [], [data]);
  const deletable = (item: FileItem) => isDeletable(item, canDelete);
  const pageSelectable = items.filter(deletable);
  const allOnPageSelected = pageSelectable.length > 0 && pageSelectable.every((item) => selected.has(item.id));

  const toggle = (item: FileItem) =>
    setSelected((current) => {
      const next = new Map(current);
      if (next.has(item.id)) next.delete(item.id);
      else next.set(item.id, item);
      return next;
    });

  const togglePage = () =>
    setSelected((current) => {
      const next = new Map(current);
      for (const item of pageSelectable) {
        if (allOnPageSelected) next.delete(item.id);
        else next.set(item.id, item);
      }
      return next;
    });

  const selectedBytes = totalBytes(selected.values());
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-4">
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          update({ q: search.trim() || undefined });
        }}
      >
        <Input
          aria-label="Search files"
          placeholder="Search by name, location, source or owner"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-72"
        />
        <Button type="submit" variant="secondary">
          Search
        </Button>
        <select aria-label="Status" className={selectClass} value={filters.status ?? ""} onChange={(e) => update({ status: e.target.value || undefined })}>
          <option value="">Any status</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select aria-label="File type" className={selectClass} value={filters.type_group ?? ""} onChange={(e) => update({ type_group: e.target.value || undefined })}>
          <option value="">Any type</option>
          {TYPE_OPTIONS.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <select
          aria-label="Size"
          className={selectClass}
          value={filters.large ? "large" : (filters.min_size ?? "").toString()}
          onChange={(e) => {
            const value = e.target.value;
            update(value === "large" ? { large: true, min_size: undefined } : { large: undefined, min_size: value ? Number(value) : undefined });
          }}
        >
          <option value="">Any size</option>
          <option value="large">Large (10 MB+)</option>
          <option value="1048576">1 MB or more</option>
          <option value="102400">100 KB or more</option>
        </select>
        {hasActiveFilters(filters) && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setSearch("");
              update({ q: undefined, status: undefined, type_group: undefined, large: undefined, min_size: undefined });
            }}
          >
            Clear filters
          </Button>
        )}
      </form>

      <nav aria-label="Folder" className="flex flex-wrap items-center gap-1 text-sm">
        <button type="button" className="text-primary hover:underline" onClick={() => update({ path: [] })}>
          All storage
        </button>
        {filters.path.map((segment, index) => (
          <span key={index} className="flex items-center gap-1">
            <ChevronRight className="h-3 w-3 text-muted-foreground" />
            <button type="button" className="text-primary hover:underline" onClick={() => update({ path: filters.path.slice(0, index + 1) })}>
              {segment}
            </button>
          </span>
        ))}
        {data && (
          <span className="ml-3 text-muted-foreground">
            {data.subtree_count} {data.subtree_count === 1 ? "file" : "files"} · {formatBytes(data.subtree_bytes)}
            {data.flat ? " matching, across all folders" : " in this folder"}
          </span>
        )}
      </nav>

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/50 px-4 py-2 text-sm" role="status">
          <span>
            {selected.size} selected · {formatBytes(selectedBytes)}
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Map())}>
              Clear selection
            </Button>
            <Button variant="destructive" size="sm" onClick={() => setDeleteIds([...selected.keys()])}>
              <Trash2 className="h-4 w-4" /> Delete selected
            </Button>
          </div>
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          {isLoading && (
            <div className="space-y-2 p-6">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          )}
          {isError && <p className="p-8 text-center text-sm text-destructive">Failed to load files. Please try again.</p>}
          {data && (
            <Table aria-busy={isFetching}>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    {canDelete && (
                      <input
                        type="checkbox"
                        aria-label="Select all deletable files on this page"
                        checked={allOnPageSelected}
                        disabled={pageSelectable.length === 0}
                        onChange={togglePage}
                      />
                    )}
                  </TableHead>
                  {SORTABLE.map((column) => (
                    <TableHead key={column.key}>
                      <button type="button" className="inline-flex items-center gap-1 font-medium" onClick={() => sortBy(column.key)}>
                        {column.label}
                        {filters.sort === column.key && (filters.order === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
                      </button>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.folders.map((folder) => (
                  <TableRow key={folder.path.join("/")} className="cursor-pointer" onClick={() => update({ path: folder.path })}>
                    <TableCell />
                    <TableCell colSpan={2}>
                      <span className="inline-flex items-center gap-2 font-medium">
                        <Folder className="h-4 w-4 text-amber-500" /> {folder.name}
                      </span>
                    </TableCell>
                    <TableCell>{formatBytes(folder.total_bytes)}</TableCell>
                    <TableCell colSpan={3} className="text-muted-foreground">
                      {folder.file_count} {folder.file_count === 1 ? "file" : "files"}
                    </TableCell>
                  </TableRow>
                ))}
                {items.map((item) => (
                  <TableRow key={item.id} className="cursor-pointer" onClick={() => setDetail(item)}>
                    <TableCell onClick={(event) => event.stopPropagation()}>
                      {canDelete && (
                        <input
                          type="checkbox"
                          aria-label={`Select ${item.name}`}
                          checked={selected.has(item.id)}
                          disabled={!deletable(item)}
                          title={deletable(item) ? undefined : "Only unused, unprotected files can be deleted"}
                          onChange={() => toggle(item)}
                        />
                      )}
                    </TableCell>
                    <TableCell className="max-w-xs">
                      <span className="inline-flex items-center gap-2 break-all font-medium">
                        {item.backend === "database" ? <HardDrive className="h-4 w-4 shrink-0 text-muted-foreground" /> : null}
                        {item.protected && <Lock className="h-3 w-3 shrink-0 text-muted-foreground" aria-label="Protected" />}
                        {item.name}
                      </span>
                      {item.is_large && <span className="ml-2 rounded bg-amber-100 px-1.5 text-xs text-amber-800">large</span>}
                    </TableCell>
                    <TableCell>{item.source_label}</TableCell>
                    <TableCell>{formatBytes(item.size_bytes)}</TableCell>
                    <TableCell>{formatDate(item.created_at)}</TableCell>
                    <TableCell>{item.owner ?? "—"}</TableCell>
                    <TableCell>
                      <StatusBadge status={item.status} />
                    </TableCell>
                  </TableRow>
                ))}
                {data.folders.length === 0 && items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                      {hasActiveFilters(filters) ? "No files match these filters." : `Nothing in ${pathLabel(filters.path)}.`}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {data && pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            Page {data.page} of {pages}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={data.page <= 1} onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}>
              Previous
            </Button>
            <Button variant="outline" size="sm" disabled={data.page >= pages} onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>
              Next
            </Button>
          </div>
        </div>
      )}

      <FileDetailsDialog
        item={detail}
        canDelete={canDelete}
        onClose={() => setDetail(null)}
        onDelete={(item) => {
          setDetail(null);
          setDeleteIds([item.id]);
        }}
      />
      <DeleteDialog
        ids={deleteIds ?? []}
        open={deleteIds !== null}
        onClose={() => setDeleteIds(null)}
        onDone={() => setSelected(new Map())}
      />
    </div>
  );
}
