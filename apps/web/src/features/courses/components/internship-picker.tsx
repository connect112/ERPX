import { internshipLabel, useLinkableInternships } from "@/features/courses/lib/linkable-internships";

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

export function InternshipPicker({
  id,
  value,
  onChange,
  exclude = [],
  disabled,
}: {
  id: string;
  value: string;
  onChange: (id: string) => void;
  /** internships already linked to this course */
  exclude?: string[];
  disabled?: boolean;
}) {
  const { internships, isLoading, isError } = useLinkableInternships();
  const options = internships.filter((i) => !exclude.includes(i.id));
  return (
    <select id={id} className={selectClass} value={value} disabled={disabled || isLoading} onChange={(e) => onChange(e.target.value)}>
      <option value="">{isError ? "Could not load internships" : "Do not link to an internship now"}</option>
      {options.map((i) => (
        <option key={i.id} value={i.id}>
          {internshipLabel(i)}
        </option>
      ))}
    </select>
  );
}
