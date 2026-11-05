import { useQuery } from "@tanstack/react-query";

import { onboardingFlowApi } from "@/features/internship-onboarding/api";
import type { OnboardingAccess } from "@/features/internship-onboarding/lib/tabs";

/** The internship's onboarding settings and what this user may do with them (one cached request for both tabs). */
export function useOnboardingConfig(internshipId: string) {
  return useQuery({ queryKey: ["onboarding-flow", internshipId, "config"], queryFn: () => onboardingFlowApi.config(internshipId) });
}

export function onboardingAccess(isAdmin: boolean, config: { can_view_finance: boolean; can_edit_finance: boolean } | undefined): OnboardingAccess {
  return { isAdmin, canViewFinance: !!config?.can_view_finance, canEditFinance: !!config?.can_edit_finance };
}
