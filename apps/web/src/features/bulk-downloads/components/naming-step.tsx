import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, FileText, Folder } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type BulkSource,
  type NamingOptions,
  type Placeholder,
  type SelectionPayload,
  type SourceInfo,
  bulkDownloadsApi,
} from "@/features/bulk-downloads/api/bulk-downloads-api";
import { insertAt, unknownPlaceholders } from "@/features/bulk-downloads/lib/template";

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";
const CUSTOM = "__custom__";

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

/** A text box with the placeholders listed under it; clicking one puts it where the cursor is. */
function TemplateField({
  id,
  label,
  value,
  onChange,
  placeholders,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholders: Placeholder[];
  hint?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const unknown = unknownPlaceholders(value, placeholders.map((p) => p.key));
  const insert = (key: string) => {
    const el = ref.current;
    const next = insertAt(value, key, el?.selectionStart ?? null, el?.selectionEnd ?? null);
    onChange(next.text);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(next.cursor, next.cursor);
    });
  };
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} ref={ref} value={value} onChange={(e) => onChange(e.target.value)} spellCheck={false} className="font-mono" />
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {unknown.length > 0 && (
        <p className="text-xs text-destructive">Not a placeholder here: {unknown.map((k) => `{{${k}}}`).join(", ")}</p>
      )}
      <div className="flex flex-wrap gap-1.5" role="group" aria-label={`Placeholders for ${label}`}>
        {placeholders.map((p) => (
          <button
            key={p.key}
            type="button"
            title={p.example ? `${p.label}, e.g. ${p.example}` : p.label}
            onClick={() => insert(p.key)}
            className={
              "rounded-full border px-2 py-0.5 font-mono text-xs hover:bg-accent " +
              (p.custom ? "border-violet-300 text-violet-700 dark:border-violet-500/40 dark:text-violet-300" : "")
            }
          >
            {`{{${p.key}}}`}
          </button>
        ))}
      </div>
    </div>
  );
}

interface Props {
  source: BulkSource;
  scopeId: string | null;
  info: SourceInfo;
  selection: SelectionPayload;
  options: NamingOptions;
  onOptions: (o: NamingOptions) => void;
  onValidity: (valid: boolean) => void;
}

export function NamingStep({ source, scopeId, info, selection, options, onOptions, onValidity }: Props) {
  const folderPreset = info.folder_presets.some((p) => p.template === options.folder_template)
    ? (options.folder_template as string)
    : options.folder_template
      ? CUSTOM
      : "";
  const [folderMode, setFolderMode] = useState<string>(folderPreset);
  const debounced = useDebounced(options, 350);
  const preview = useQuery({
    queryKey: ["bulk-downloads", "preview", source, scopeId, debounced, selection],
    queryFn: () => bulkDownloadsApi.preview(source, scopeId, debounced, selection),
    enabled: debounced.filename_template.trim().length > 0,
    placeholderData: (previous) => previous,
  });
  const settled = debounced === options && !preview.isFetching;
  const valid = settled && preview.data?.valid === true;
  useEffect(() => onValidity(valid), [valid, onValidity]);

  const presetValue = info.presets.find((p) => p.template === options.filename_template)?.template ?? CUSTOM;
  const extensionHint = info.extension
    ? `Files are .${info.extension}; the extension is added if you leave it off.`
    : "Each file keeps its own extension, so leave it off.";

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_minmax(0,22rem)]">
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="bulk-preset">File name format</Label>
          <select
            id="bulk-preset"
            className={selectClass}
            value={presetValue}
            onChange={(e) => e.target.value !== CUSTOM && onOptions({ ...options, filename_template: e.target.value })}
          >
            {info.presets.map((p) => (
              <option key={p.template} value={p.template}>
                {p.label}: {p.template}
              </option>
            ))}
            <option value={CUSTOM}>Custom…</option>
          </select>
        </div>
        <TemplateField
          id="bulk-filename"
          label="File name"
          value={options.filename_template}
          onChange={(v) => onOptions({ ...options, filename_template: v })}
          placeholders={info.placeholders}
          hint={`${extensionHint} Purple placeholders come from this ${info.document_type.toLowerCase()}'s own fields.`}
        />

        <div className="space-y-1.5">
          <Label htmlFor="bulk-folders">Folders inside the ZIP</Label>
          <select
            id="bulk-folders"
            className={selectClass}
            value={folderMode}
            onChange={(e) => {
              setFolderMode(e.target.value);
              onOptions({ ...options, folder_template: e.target.value === CUSTOM ? options.folder_template || "" : e.target.value });
            }}
          >
            <option value="">No folders (all files together)</option>
            {info.folder_presets.map((p) => (
              <option key={p.template} value={p.template}>
                {p.label}
              </option>
            ))}
            <option value={CUSTOM}>Custom…</option>
          </select>
        </div>
        {folderMode === CUSTOM && (
          <TemplateField
            id="bulk-folder-template"
            label="Folder format"
            value={options.folder_template ?? ""}
            onChange={(v) => onOptions({ ...options, folder_template: v })}
            placeholders={info.placeholders}
            hint="Use / for sub-folders, at most three levels, e.g. {{program_name}}/{{certificate_type}}."
          />
        )}

        <TemplateField
          id="bulk-zip"
          label="ZIP file name"
          value={options.zip_template ?? ""}
          onChange={(v) => onOptions({ ...options, zip_template: v })}
          placeholders={info.zip_placeholders}
          hint=".zip is added for you."
        />
      </div>

      <div className="space-y-2 rounded-md border bg-muted/30 p-3 text-sm" aria-live="polite">
        <div className="font-medium">Preview</div>
        {preview.data && !preview.data.valid && <p className="text-destructive">{preview.data.error}</p>}
        {preview.isError && <p className="text-destructive">The preview could not be made.</p>}
        {preview.data?.valid && (
          <>
            <div className="flex items-center gap-1.5 font-mono text-xs">
              <Folder className="h-3.5 w-3.5 shrink-0" />
              <span className="break-all">{preview.data.zip_filename}</span>
              <span className="text-muted-foreground">({preview.data.total} files)</span>
            </div>
            <ul className="space-y-1 pl-4">
              {preview.data.files.map((f) => (
                <li key={f.id} className="flex items-start gap-1.5 font-mono text-xs">
                  <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span className="break-all">{f.path}</span>
                </li>
              ))}
              {preview.data.total > preview.data.files.length && (
                <li className="text-xs text-muted-foreground">…and {preview.data.total - preview.data.files.length} more</li>
              )}
            </ul>
            {preview.data.renamed_duplicates > 0 && (
              <p className="text-xs text-muted-foreground">
                {preview.data.renamed_duplicates} name(s) repeat, so they get _2, _3… to stay unique.
              </p>
            )}
            {preview.data.warnings.map((w) => (
              <p key={w} className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                {w}
              </p>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
