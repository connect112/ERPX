import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { errorMessage } from "@/features/institutions/lib/format";
import { onboardingFlowApi } from "@/features/internship-onboarding/api";
import { PaymentsQueue } from "@/features/internship-onboarding/components/payments-queue";
import { SettingsEditor } from "@/features/internship-onboarding/components/settings-editor";
import { StudentsBoard } from "@/features/internship-onboarding/components/students-board";

/** Automated onboarding, above the existing manual tools (which keep working whatever is chosen here). */
export function OnboardingFlowPanel({ internshipId, canManage }: { internshipId: string; canManage: boolean }) {
  const config = useQuery({ queryKey: ["onboarding-flow", internshipId, "config"], queryFn: () => onboardingFlowApi.config(internshipId) });
  const manual = config.data?.settings.modes.mode === "manual";
  const [tab, setTab] = useState<string | null>(null);
  const active = tab ?? (manual ? "settings" : "students");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Student self-service onboarding</CardTitle>
        <CardDescription>
          {manual
            ? "Off: onboarding is recorded by staff below. Choose automated or hybrid in Settings to send students personal links."
            : "Each student gets a personal link to confirm details, upload documents, accept the offer and pay."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {config.isError && <p className="text-sm text-destructive">{errorMessage(config.error, "Could not load the onboarding settings.")}</p>}
        {config.data && (
          <Tabs value={active} onValueChange={setTab}>
            <TabsList className="h-auto flex-wrap justify-start">
              <TabsTrigger value="students">Students</TabsTrigger>
              <TabsTrigger value="payments">Payment checks</TabsTrigger>
              {canManage && <TabsTrigger value="settings">Settings</TabsTrigger>}
            </TabsList>
            <TabsContent value="students">
              <StudentsBoard internshipId={internshipId} timezone={config.data.settings.deadlines.timezone} canManage={canManage && !manual} />
            </TabsContent>
            <TabsContent value="payments">
              <PaymentsQueue internshipId={internshipId} />
            </TabsContent>
            {canManage && (
              <TabsContent value="settings">
                <SettingsEditor internshipId={internshipId} view={config.data} />
              </TabsContent>
            )}
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
