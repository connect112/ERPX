import { useMutation, useQuery } from "@tanstack/react-query";

import { myPayslipsApi } from "@/features/employee-self-service/api/payslips-api";

export function useMyPayslips() {
  return useQuery({
    queryKey: ["payroll", "payslips", "me"],
    queryFn: () => myPayslipsApi.myPayslips(),
  });
}

export function useOpenPayslipPdf() {
  return useMutation({
    mutationFn: async (payslipId: string) => {
      const blob = await myPayslipsApi.getPayslipPdf(payslipId);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      // Revoked after a delay rather than immediately — the new tab needs
      // the blob URL to still be valid by the time it finishes loading it.
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    },
  });
}
