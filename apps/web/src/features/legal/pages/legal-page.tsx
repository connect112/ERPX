import { Link } from "react-router-dom";

import { COMPANY, DATA_DELETION, PRIVACY_POLICY, type LegalDocument } from "@/features/legal/lib/legal-content";

function Document({ doc }: { doc: LegalDocument }) {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <p className="text-sm text-muted-foreground">{COMPANY}</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight">{doc.title}</h1>
      <p className="mt-1 text-sm text-muted-foreground">Last updated {doc.updated}</p>
      <p className="mt-6 leading-relaxed">{doc.intro}</p>
      {doc.sections.map((s) => (
        <section key={s.heading} className="mt-8 space-y-3">
          <h2 className="text-xl font-semibold">{s.heading}</h2>
          {s.paragraphs?.map((p) => (
            <p key={p} className="leading-relaxed">
              {p}
            </p>
          ))}
          {s.items && (
            <ul className="list-disc space-y-1.5 pl-6 leading-relaxed">
              {s.items.map((i) => (
                <li key={i}>{i}</li>
              ))}
            </ul>
          )}
        </section>
      ))}
      <nav className="mt-12 flex flex-wrap gap-4 border-t pt-6 text-sm" aria-label="Legal pages">
        <Link className="text-primary underline" to="/privacy">
          Privacy Policy
        </Link>
        <Link className="text-primary underline" to="/data-deletion">
          Data Deletion
        </Link>
        <Link className="text-primary underline" to="/login">
          Sign in
        </Link>
      </nav>
    </main>
  );
}

/** Public, no login: Meta (and anyone else) must be able to open these. */
export function PrivacyPolicyPage() {
  return <Document doc={PRIVACY_POLICY} />;
}

export function DataDeletionPage() {
  return <Document doc={DATA_DELETION} />;
}
