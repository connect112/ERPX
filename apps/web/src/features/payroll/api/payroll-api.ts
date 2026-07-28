import { apiClient } from "@/api/client";
import type { PayrollRunStatus, SalaryComponentType } from "@/features/payroll/schemas/payroll-schemas";

export interface SalaryComponentPublic {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  gl_account_id: string;
  component_type: SalaryComponentType;
  is_taxable: boolean;
  is_active: boolean;
  created_at: string;
}

export interface SalaryComponentCreatePayload {
  name: string;
  code: string;
  gl_account_id: string;
  component_type: SalaryComponentType;
  is_taxable?: boolean;
}

export type SalaryComponentUpdatePayload = Partial<Omit<SalaryComponentCreatePayload, "code">> & {
  is_active?: boolean;
};

export interface SalaryStructureLinePublic {
  id: string;
  salary_component_id: string;
  amount: number;
}

export interface SalaryStructurePublic {
  id: string;
  organization_id: string;
  employee_id: string;
  effective_from: string;
  notes: string | null;
  gross_monthly_amount: number;
  total_deductions: number;
  net_monthly_amount: number;
  is_active: boolean;
  lines: SalaryStructureLinePublic[];
  created_at: string;
}

export interface SalaryStructureLinePayload {
  salary_component_id: string;
  amount: number;
}

export interface SalaryStructureCreatePayload {
  employee_id: string;
  effective_from: string;
  notes?: string;
  lines: SalaryStructureLinePayload[];
}

export interface PayrollRunPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  period_year: number;
  period_month: number;
  run_date: string;
  status: PayrollRunStatus;
  total_gross_amount: number;
  total_deductions_amount: number;
  total_net_amount: number;
  finalized_at: string | null;
  paid_at: string | null;
  net_payable_account_id: string | null;
  bank_account_id: string | null;
  journal_entry_id: string | null;
  payment_journal_entry_id: string | null;
  created_at: string;
}

export interface PayrollRunListResponse {
  items: PayrollRunPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface PayrollRunListParams {
  status?: PayrollRunStatus;
  skip?: number;
  limit?: number;
}

export interface PayrollRunGeneratePayload {
  period_year: number;
  period_month: number;
  run_date: string;
  branch_id?: string;
}

export interface PayrollRunGenerationResult {
  run: PayrollRunPublic;
  employees_processed: number;
  employees_skipped_no_structure: string[];
}

export interface PayslipLinePublic {
  salary_component_id: string;
  component_type: SalaryComponentType;
  amount: number;
}

export interface PayslipPublic {
  id: string;
  organization_id: string;
  payroll_run_id: string;
  employee_id: string;
  days_in_month: number;
  paid_days: number;
  lop_days: number;
  gross_amount: number;
  total_deductions: number;
  net_amount: number;
  lines: PayslipLinePublic[];
  created_at: string;
}

export interface PayslipListResponse {
  items: PayslipPublic[];
  total: number;
  skip: number;
  limit: number;
}

export const payrollApi = {
  listComponents: (isActive?: boolean) =>
    apiClient
      .get<SalaryComponentPublic[]>("/payroll/components", { params: { is_active: isActive } })
      .then((r) => r.data),

  createComponent: (payload: SalaryComponentCreatePayload) =>
    apiClient.post<SalaryComponentPublic>("/payroll/components", payload).then((r) => r.data),

  updateComponent: (id: string, payload: SalaryComponentUpdatePayload) =>
    apiClient.patch<SalaryComponentPublic>(`/payroll/components/${id}`, payload).then((r) => r.data),

  createStructure: (payload: SalaryStructureCreatePayload) =>
    apiClient.post<SalaryStructurePublic>("/payroll/structures", payload).then((r) => r.data),

  getStructure: (id: string) =>
    apiClient.get<SalaryStructurePublic>(`/payroll/structures/${id}`).then((r) => r.data),

  listStructuresByEmployee: (employeeId: string) =>
    apiClient
      .get<SalaryStructurePublic[]>(`/payroll/structures/employees/${employeeId}`)
      .then((r) => r.data),

  generateRun: (payload: PayrollRunGeneratePayload) =>
    apiClient.post<PayrollRunGenerationResult>("/payroll/runs", payload).then((r) => r.data),

  listRuns: (params: PayrollRunListParams) =>
    apiClient.get<PayrollRunListResponse>("/payroll/runs", { params }).then((r) => r.data),

  getRun: (id: string) => apiClient.get<PayrollRunPublic>(`/payroll/runs/${id}`).then((r) => r.data),

  listPayslips: (runId: string) =>
    apiClient.get<PayslipPublic[]>(`/payroll/runs/${runId}/payslips`).then((r) => r.data),

  finalizeRun: (id: string, netPayableAccountId: string) =>
    apiClient
      .post<PayrollRunPublic>(`/payroll/runs/${id}/finalize`, { net_payable_account_id: netPayableAccountId })
      .then((r) => r.data),

  markRunPaid: (id: string, bankAccountId: string, paymentDate: string) =>
    apiClient
      .post<PayrollRunPublic>(`/payroll/runs/${id}/mark-paid`, {
        bank_account_id: bankAccountId,
        payment_date: paymentDate,
      })
      .then((r) => r.data),

  cancelRun: (id: string) =>
    apiClient.post<PayrollRunPublic>(`/payroll/runs/${id}/cancel`).then((r) => r.data),

  getPayslip: (id: string) => apiClient.get<PayslipPublic>(`/payroll/payslips/${id}`).then((r) => r.data),

  listPayslipsByEmployee: (employeeId: string, params: { skip?: number; limit?: number }) =>
    apiClient
      .get<PayslipListResponse>(`/payroll/payslips/employees/${employeeId}`, { params })
      .then((r) => r.data),
};
