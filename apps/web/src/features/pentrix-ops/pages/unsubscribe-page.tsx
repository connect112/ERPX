import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { apiClient } from "@/api/client";
import { Button } from "@/components/ui/button";

interface Info {
  email: string;
  unsubscribed: boolean;
}

const base = "/public/pentrix-marketing/unsubscribe";

/** Where the unsubscribe link in a Pentrix marketing email lands. No sign-in: the link itself proves whose address it is. */
export function UnsubscribePage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const info = useQuery({
    queryKey: ["pentrix-unsubscribe", token],
    queryFn: () => apiClient.get<Info>(base, { params: { token } }).then((r) => r.data),
    enabled: !!token,
    retry: false,
  });
  const unsubscribe = useMutation({ mutationFn: () => apiClient.post<Info>(base, null, { params: { token } }).then((r) => r.data) });
  const invalid = !token || info.isError;

  return (
    <div className="min-h-screen bg-muted/30">
      <div className="mx-auto max-w-md px-4 py-16">
        <div className="rounded-lg border bg-card p-8 text-center">
          <p className="text-sm font-medium text-muted-foreground">Pentrix</p>
          {info.isLoading && token && <p className="mt-4 text-muted-foreground">Checking your link…</p>}
          {invalid && !info.isLoading && (
            <>
              <h1 className="mt-2 text-xl font-semibold">This link is not valid</h1>
              <p className="mt-3 text-sm text-muted-foreground">
                It may be incomplete or damaged. Use the unsubscribe link in the email, or turn marketing email off in Settings in your Pentrix portal.
              </p>
            </>
          )}
          {info.data && !unsubscribe.isSuccess && (
            <>
              <h1 className="mt-2 text-xl font-semibold">Stop Pentrix marketing emails?</h1>
              <p className="mt-3 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{info.data.email}</span> will no longer receive updates and offers from Pentrix. You will still get messages about
                your account, appointments and payments.
              </p>
              {unsubscribe.isError && <p role="alert" className="mt-3 text-sm text-destructive">Something went wrong. Please try again.</p>}
              <Button className="mt-6" disabled={unsubscribe.isPending} onClick={() => unsubscribe.mutate()}>
                {unsubscribe.isPending ? "Unsubscribing…" : "Unsubscribe"}
              </Button>
            </>
          )}
          {unsubscribe.isSuccess && (
            <>
              <h1 className="mt-2 text-xl font-semibold">You are unsubscribed</h1>
              <p className="mt-3 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{unsubscribe.data.email}</span> will not receive Pentrix marketing emails. You can turn them back on any time in
                Settings in your Pentrix portal.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
