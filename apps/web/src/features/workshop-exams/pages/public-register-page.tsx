import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { type PublicJoinInfo, publicExamApi } from "@/features/workshop-exams/api/workshop-exams-api";

function errorText(error: unknown, fallback: string): string {
  return (
    (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? fallback
  );
}

/**
 * The shared, login-free page an organiser hands out for a workshop exam.
 * Students fill in the details the admin asked for and are sent straight
 * into their own private exam link (which is also emailed to them).
 */
export function PublicRegisterPage() {
  const { code = "" } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [join, setJoin] = useState<PublicJoinInfo | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [info, setInfo] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alreadyRegistered, setAlreadyRegistered] = useState(false);

  useEffect(() => {
    let cancelled = false;
    publicExamApi
      .joinInfo(code)
      .then((data) => !cancelled && setJoin(data))
      .catch(() => !cancelled && setInvalid(true));
    return () => {
      cancelled = true;
    };
  }, [code]);

  const shell = (children: React.ReactNode) => (
    <div className="min-h-screen bg-muted/30">
      <div className="mx-auto max-w-xl px-4 py-8">{children}</div>
    </div>
  );

  if (invalid)
    return shell(
      <div className="rounded-lg border bg-card p-8 text-center">
        <h1 className="text-xl font-semibold">This link isn't valid</h1>
        <p className="mt-2 text-sm text-muted-foreground">Please check the link with the organiser.</p>
      </div>
    );
  if (!join) return shell(<p className="text-center text-muted-foreground">Loading...</p>);

  if (alreadyRegistered)
    return shell(
      <div className="rounded-lg border bg-card p-8 text-center">
        <h1 className="text-xl font-semibold">You're already registered</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Your personal exam link was sent to {email.trim().toLowerCase()}. Open it from your inbox (check spam too)
          to continue. If it isn't there in a couple of minutes, ask the organiser.
        </p>
      </div>
    );

  const missing =
    !name.trim() ||
    !email.trim() ||
    join.info_fields.some((f) => f.required && !(info[f.key] ?? "").trim());

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await publicExamApi.register(code, { name: name.trim(), email: email.trim(), info });
      if (result.already_registered || !result.token) setAlreadyRegistered(true);
      else navigate(`/workshop-exam/${result.token}`);
    } catch (e) {
      setError(errorText(e, "Could not register. Please check your details and try again."));
    } finally {
      setBusy(false);
    }
  };

  return shell(
    <form
      className="space-y-4 rounded-lg border bg-card p-8"
      onSubmit={(e) => {
        e.preventDefault();
        if (!missing && join.state === "open") void submit();
      }}
    >
      <div>
        <h1 className="text-xl font-semibold">{join.title}</h1>
        {join.description && <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{join.description}</p>}
        <p className="mt-2 text-sm text-muted-foreground">
          {join.question_count} questions · {join.duration_minutes} minutes
        </p>
      </div>

      {join.state === "not_open" && (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
          Registration hasn't opened yet. Please wait for the organiser, then refresh this page.
        </p>
      )}
      {join.state === "closed" && <p className="rounded-md bg-muted p-3 text-sm">This exam is closed.</p>}

      {join.state === "open" && (
        <>
          <div className="space-y-2">
            <Label htmlFor="r-name">Full name * (in English letters, exactly as it should appear on your certificate)</Label>
            <Input id="r-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="r-email">Email * (your certificate is sent here)</Label>
            <Input
              id="r-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>
          {join.info_fields.map((f) => (
            <div key={f.key} className="space-y-2">
              <Label htmlFor={`r-${f.key}`}>
                {f.label}
                {f.required && " *"}
              </Label>
              {f.type === "select" ? (
                <select
                  id={`r-${f.key}`}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  value={info[f.key] ?? ""}
                  onChange={(e) => setInfo({ ...info, [f.key]: e.target.value })}
                >
                  <option value="">Select...</option>
                  {f.options.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  id={`r-${f.key}`}
                  type={f.type === "phone" ? "tel" : "text"}
                  value={info[f.key] ?? ""}
                  onChange={(e) => setInfo({ ...info, [f.key]: e.target.value })}
                />
              )}
            </div>
          ))}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" size="lg" className="w-full" disabled={missing || busy}>
            {busy ? "Registering..." : "Continue to the exam"}
          </Button>
        </>
      )}
    </form>
  );
}
