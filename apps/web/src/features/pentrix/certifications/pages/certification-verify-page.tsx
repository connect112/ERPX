import { CheckCircle2, Search, XCircle } from "lucide-react";
import { useState } from "react";

import { apiClient } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { CertificationVerificationResponse } from "@/features/pentrix/certifications/api/certifications-api";

export function CertificationVerifyPage() {
  const [certificateNumber, setCertificateNumber] = useState("");
  const [result, setResult] = useState<CertificationVerificationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onVerify = async () => {
    if (!certificateNumber.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const { data } = await apiClient.get<CertificationVerificationResponse>(
        `/pentrix/certifications/verify/${encodeURIComponent(certificateNumber.trim())}`
      );
      setResult(data);
    } catch {
      setError("Unable to verify this certificate right now. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Verify a Pentrix Certification</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Certificate number"
              value={certificateNumber}
              onChange={(e) => setCertificateNumber(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onVerify()}
            />
            <Button onClick={onVerify} disabled={loading}>
              <Search className="h-4 w-4" />
              {loading ? "Checking..." : "Verify"}
            </Button>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          {result && result.valid && (
            <div className="flex items-start gap-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-4">
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
              <div className="text-sm">
                <p className="font-medium text-emerald-700 dark:text-emerald-400">
                  Certification verified
                </p>
                {result.student_name && <p className="mt-1">Student: {result.student_name}</p>}
                {result.track_name && <p>Track: {result.track_name}</p>}
                {result.points_at_issuance !== null && (
                  <p>Points at issuance: {result.points_at_issuance}</p>
                )}
                {result.issued_at && (
                  <p>Issued: {new Date(result.issued_at).toLocaleDateString()}</p>
                )}
              </div>
            </div>
          )}

          {result && !result.valid && (
            <div className="flex items-center gap-3 rounded-md border border-destructive/30 bg-destructive/10 p-4">
              <XCircle className="h-5 w-5 shrink-0 text-destructive" />
              <p className="text-sm font-medium text-destructive">
                This certificate number could not be verified.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
