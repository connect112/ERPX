import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { CandidateFilters } from "@/features/pentrix-ops/api/candidates-api";
import { selectClass } from "@/features/our-internships/components/letter-fields";

const ASSESSMENT = [["", "Any"], ["not_started", "Not started"], ["in_progress", "In progress"], ["completed", "Completed"], ["pending", "Not completed"]];
const QUALIFICATION = [["", "Any"], ["qualified", "Qualified"], ["not_qualified", "Not qualified"], ["pending", "No result yet"]];
const BOOKING = [["", "Any"], ["scheduled", "Booking scheduled"], ["not_scheduled", "No booking scheduled"], ["completed", "Completed"], ["cancelled", "Cancelled"], ["no_show", "No show"]];
const PAYMENT = [["", "Any"], ["paid", "Paid"], ["not_paid", "Not paid"], ["pending", "Payment pending"], ["failed", "Payment failed"], ["refunded", "Refunded"], ["none", "No payment made"]];

function Pick({ id, label, value, options, onChange }: { id: string; label: string; value: string; options: string[][]; onChange: (v: string) => void }) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <select id={id} className={`${selectClass} w-44`} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map(([v, l]) => (
          <option key={v} value={v}>{l}</option>
        ))}
      </select>
    </div>
  );
}

export function CandidateFilterBar({
  idPrefix, filters, update, clear, active, sorts,
}: {
  idPrefix: string;
  filters: CandidateFilters;
  update: (patch: Partial<CandidateFilters>) => void;
  clear: () => void;
  active: boolean;
  sorts: string[][];
}) {
  const [search, setSearch] = useState(filters.q);
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        update({ q: search.trim() });
      }}
    >
      <div className="space-y-1">
        <Label htmlFor={`${idPrefix}-search`}>Search</Label>
        <Input id={`${idPrefix}-search`} className="w-56" placeholder="Name, email or phone" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <Pick id={`${idPrefix}-assessment`} label="Assessment" value={filters.assessment} options={ASSESSMENT} onChange={(v) => update({ assessment: v })} />
      <Pick id={`${idPrefix}-qualification`} label="Qualification" value={filters.qualification} options={QUALIFICATION} onChange={(v) => update({ qualification: v })} />
      <Pick id={`${idPrefix}-booking`} label="Booking" value={filters.booking} options={BOOKING} onChange={(v) => update({ booking: v })} />
      <Pick id={`${idPrefix}-payment`} label="Payment" value={filters.payment} options={PAYMENT} onChange={(v) => update({ payment: v })} />
      <div className="space-y-1">
        <Label htmlFor={`${idPrefix}-from`}>Registered from</Label>
        <Input id={`${idPrefix}-from`} type="date" className="w-40" value={filters.registered_from} onChange={(e) => update({ registered_from: e.target.value })} />
      </div>
      <div className="space-y-1">
        <Label htmlFor={`${idPrefix}-to`}>Registered to</Label>
        <Input id={`${idPrefix}-to`} type="date" className="w-40" value={filters.registered_to} onChange={(e) => update({ registered_to: e.target.value })} />
      </div>
      <Pick id={`${idPrefix}-sort`} label="Sort by" value={filters.sort} options={sorts} onChange={(v) => update({ sort: v })} />
      <Pick id={`${idPrefix}-order`} label="Order" value={filters.order} options={[["desc", "Newest / highest first"], ["asc", "Oldest / lowest first"]]} onChange={(v) => update({ order: v as "asc" | "desc" })} />
      <Button type="submit" variant="outline">Search</Button>
      {active && (
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            setSearch("");
            clear();
          }}
        >
          Clear filters
        </Button>
      )}
    </form>
  );
}
