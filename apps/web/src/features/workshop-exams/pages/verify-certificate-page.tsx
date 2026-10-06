import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { publicExamApi } from "@/features/workshop-exams/api/workshop-exams-api";

/** Where the QR code on a workshop certificate lands. */
export function VerifyWorkshopCertificatePage() {
  const { number = "" } = useParams<{ number: string }>();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["workshop-certificate", number],
    queryFn: () => publicExamApi.verifyCertificate(number),
    retry: 1,
  });

  return (
    <div className="min-h-screen bg-muted/30">
      <div className="mx-auto max-w-md px-4 py-16">
        <div className="rounded-lg border bg-card p-8 text-center">
          {isLoading ? (
            <p className="text-muted-foreground">Checking...</p>
          ) : isError ? (
            <p className="text-destructive">Could not check this certificate right now. Please try again.</p>
          ) : data?.valid ? (
            <>
              <p className="text-sm font-medium text-emerald-700">Valid certificate</p>
              <h1 className="mt-2 text-2xl font-semibold">{data.attendee_name}</h1>
              <p className="mt-2 text-sm text-muted-foreground">{data.exam_title}</p>
              {data.issued_at && (
                <p className="mt-1 text-sm text-muted-foreground">
                  Issued {new Date(data.issued_at).toLocaleDateString(undefined, { dateStyle: "long" })}
                </p>
              )}
              <p className="mt-4 font-mono text-xs text-muted-foreground">{number}</p>
            </>
          ) : (
            <>
              <p className="text-sm font-medium text-destructive">Not found</p>
              <p className="mt-2 text-sm text-muted-foreground">
                No certificate with number {number} was issued by us.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
