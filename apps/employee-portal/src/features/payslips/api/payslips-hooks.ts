import { useQuery } from "@tanstack/react-query";

import { payslipsApi } from "@/features/payslips/api/payslips-api";

export function useMyPayslips() {
  return useQuery({
    queryKey: ["payroll", "payslips", "me"],
    queryFn: () => payslipsApi.myPayslips(),
  });
}
