import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type PayrollRunGeneratePayload,
  type PayrollRunListParams,
  type SalaryComponentCreatePayload,
  type SalaryComponentUpdatePayload,
  type SalaryStructureCreatePayload,
  payrollApi,
} from "@/features/payroll/api/payroll-api";

const componentsKey = ["payroll", "components"] as const;
const structuresKeys = {
  all: ["payroll", "structures"] as const,
  detail: (id: string) => [...structuresKeys.all, "detail", id] as const,
  byEmployee: (employeeId: string) => [...structuresKeys.all, "employee", employeeId] as const,
};
const runsKeys = {
  all: ["payroll", "runs"] as const,
  list: (params: PayrollRunListParams) => [...runsKeys.all, "list", params] as const,
  detail: (id: string) => [...runsKeys.all, "detail", id] as const,
  payslips: (runId: string) => [...runsKeys.all, runId, "payslips"] as const,
};
const employeePayslipsKey = (employeeId: string, params: { skip?: number; limit?: number }) =>
  ["payroll", "payslips", "employee", employeeId, params] as const;

export function useSalaryComponents(isActive?: boolean) {
  return useQuery({
    queryKey: [...componentsKey, isActive],
    queryFn: () => payrollApi.listComponents(isActive),
  });
}

export function useCreateSalaryComponent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SalaryComponentCreatePayload) => payrollApi.createComponent(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: componentsKey }),
  });
}

export function useUpdateSalaryComponent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SalaryComponentUpdatePayload }) =>
      payrollApi.updateComponent(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: componentsKey }),
  });
}

export function useEmployeeSalaryStructures(employeeId: string | undefined) {
  return useQuery({
    queryKey: structuresKeys.byEmployee(employeeId ?? ""),
    queryFn: () => payrollApi.listStructuresByEmployee(employeeId as string),
    enabled: !!employeeId,
  });
}

export function useCreateSalaryStructure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SalaryStructureCreatePayload) => payrollApi.createStructure(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: structuresKeys.all }),
  });
}

export function usePayrollRuns(params: PayrollRunListParams) {
  return useQuery({
    queryKey: runsKeys.list(params),
    queryFn: () => payrollApi.listRuns(params),
    placeholderData: keepPreviousData,
  });
}

export function usePayrollRun(id: string | undefined) {
  return useQuery({
    queryKey: runsKeys.detail(id ?? ""),
    queryFn: () => payrollApi.getRun(id as string),
    enabled: !!id,
  });
}

export function useRunPayslips(runId: string | undefined) {
  return useQuery({
    queryKey: runsKeys.payslips(runId ?? ""),
    queryFn: () => payrollApi.listPayslips(runId as string),
    enabled: !!runId,
  });
}

export function useGeneratePayrollRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PayrollRunGeneratePayload) => payrollApi.generateRun(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: runsKeys.all }),
  });
}

export function useFinalizePayrollRun(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (netPayableAccountId: string) => payrollApi.finalizeRun(id, netPayableAccountId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: runsKeys.all }),
  });
}

export function useMarkPayrollRunPaid(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ bankAccountId, paymentDate }: { bankAccountId: string; paymentDate: string }) =>
      payrollApi.markRunPaid(id, bankAccountId, paymentDate),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: runsKeys.all }),
  });
}

export function useCancelPayrollRun(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => payrollApi.cancelRun(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: runsKeys.all }),
  });
}

export function useEmployeePayslips(employeeId: string | undefined, params: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: employeePayslipsKey(employeeId ?? "", params),
    queryFn: () => payrollApi.listPayslipsByEmployee(employeeId as string, params),
    enabled: !!employeeId,
    placeholderData: keepPreviousData,
  });
}
