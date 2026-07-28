import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useTDSDeductionsForVendor, useTDSSections } from "@/features/accounting/tds/api/tds-hooks";

export function VendorTDSDeductionsPanel({ vendorId }: { vendorId: string }) {
  const { data: deductions, isLoading } = useTDSDeductionsForVendor(vendorId);
  const { data: sections } = useTDSSections();

  const sectionLabel = (id: string) => sections?.find((s) => s.id === id)?.section_code ?? id;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">TDS Deductions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (deductions?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No TDS deductions recorded for this vendor.</p>
        )}
        {deductions?.map((deduction) => (
          <div key={deduction.id} className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">{sectionLabel(deduction.tds_section_id)}</p>
              <p className="text-xs text-muted-foreground">
                {deduction.financial_year} ·{" "}
                {new Date(deduction.deduction_date).toLocaleDateString()}
              </p>
            </div>
            <div className="text-right text-sm">
              <p>Gross: ₹{deduction.gross_amount}</p>
              <p className="text-muted-foreground">TDS: ₹{deduction.tds_amount}</p>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
