import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { usePlaceholders } from "@/features/email-studio/api/studio-api";
import { groupPlaceholders, token } from "@/features/email-studio/lib/studio";

/**
 * Every placeholder an email can use, grouped and searchable. Choosing one types it where the cursor was last (the subject, the
 * design or the HTML). For an email that stands in for an ERPX email, only the values that email supplies are shown.
 */
export function PlaceholderPicker({ erpxKey, onInsert }: { erpxKey: string | null; onInsert: (text: string) => void }) {
  const list = usePlaceholders(erpxKey);
  const [query, setQuery] = useState("");
  const groups = useMemo(() => groupPlaceholders(list.data ?? [], query), [list.data, query]);

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <Input aria-label="Search placeholders" placeholder="Search placeholders" className="pl-8" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <p className="text-xs text-muted-foreground">Click one to type it where your cursor was. It is replaced with the real value when the email is sent.</p>
      {list.isLoading && <Skeleton className="h-32 w-full" />}
      {groups.length === 0 && !list.isLoading && <p className="text-sm text-muted-foreground">No placeholder matches.</p>}
      {groups.map(([group, items]) => (
        <section key={group} aria-label={group}>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{group}</h4>
          <ul className="space-y-1">
            {items.map((p) => (
              <li key={p.name}>
                <button
                  type="button"
                  className="w-full rounded-md border px-2 py-1.5 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onMouseDown={(e) => e.preventDefault()} // keep the cursor where it was
                  onClick={() => onInsert(token(p.name))}
                  title={p.sample ? `Example: ${p.sample}` : undefined}
                >
                  <code className="text-xs">{token(p.name)}</code>
                  <span className="block text-xs text-muted-foreground">{p.description}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
