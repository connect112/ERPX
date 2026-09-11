import { apiClient } from "@/api/client";

export interface PayslipLine {
  id: string;
  salary_component_id: string;
  component_type: "earning" | "deduction";
  amount: number;
}

export interface Payslip {
  id: string;
  payroll_run_id: string;
  employee_id: string;
  salary_structure_id: string;
  days_in_month: number;
  paid_days: number;
  lop_days: number;
  gross_amount: number;
  total_deductions: number;
  net_amount: number;
  created_at: string;
  lines: PayslipLine[];
}

export interface PayslipListResponse {
  items: Payslip[];
  total: number;
  skip: number;
  limit: number;
}

export const payslipsApi = {
  myPayslips: () => apiClient.get<PayslipListResponse>("/payroll/payslips/me").then((r) => r.data),
};
