import { ArrowLeft, PackageX, Pencil } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAccountsList } from "@/features/accounting/ledger/api/accounts-hooks";
import { useAssetCategories } from "@/features/assets/categories/api/asset-categories-hooks";
import { depreciationMethodLabels } from "@/features/assets/categories/schemas/asset-category-schemas";
import { useAsset, useAssetNetBookValue } from "@/features/assets/assets/api/assets-hooks";
import { AssetEditDialog } from "@/features/assets/assets/components/asset-edit-dialog";
import { AssetStatusBadge } from "@/features/assets/assets/components/asset-status-badge";
import { DisposeAssetDialog } from "@/features/assets/assets/components/dispose-asset-dialog";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function AssetDetailPage() {
  const { assetId } = useParams<{ assetId: string }>();
  const navigate = useNavigate();
  const { data: asset, isLoading } = useAsset(assetId);
  const { data: nbv } = useAssetNetBookValue(assetId);
  const { data: categories } = useAssetCategories();
  const { data: accounts } = useAccountsList({ limit: 200 });
  const { data: employees } = useEmployeesList({ limit: 200 });

  const [editOpen, setEditOpen] = useState(false);
  const [disposeOpen, setDisposeOpen] = useState(false);

  if (isLoading || !asset) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const categoryName = categories?.find((c) => c.id === asset.category_id)?.name;
  const assignedEmployeeName = employees?.items.find((e) => e.id === asset.assigned_to_employee_id)?.full_name;
  const accountName = (id: string) => {
    const account = accounts?.items.find((a) => a.id === id);
    return account ? `${account.code} — ${account.name}` : id;
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/assets")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{asset.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{asset.asset_code}</span>
              <AssetStatusBadge status={asset.status} />
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
            Edit
          </Button>
          {asset.status !== "disposed" && (
            <Button variant="outline" onClick={() => setDisposeOpen(true)}>
              <PackageX className="h-4 w-4" />
              Dispose
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Asset details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Category" value={categoryName || "—"} />
              <DetailRow label="Assigned to" value={assignedEmployeeName || "—"} />
              <DetailRow label="Location" value={asset.location || "—"} />
              <DetailRow label="Purchase date" value={new Date(asset.purchase_date).toLocaleDateString()} />
              <DetailRow label="Purchase cost" value={asset.purchase_cost.toLocaleString()} />
              <DetailRow label="Salvage value" value={asset.salvage_value.toLocaleString()} />
              <DetailRow label="Useful life" value={`${asset.useful_life_years} years`} />
              <DetailRow
                label="Depreciation method"
                value={depreciationMethodLabels[asset.depreciation_method]}
              />
              <DetailRow label="Asset account" value={accountName(asset.asset_account_id)} />
              <DetailRow
                label="Accumulated depreciation account"
                value={accountName(asset.accumulated_depreciation_account_id)}
              />
              <DetailRow
                label="Depreciation expense account"
                value={accountName(asset.depreciation_expense_account_id)}
              />
              {asset.status === "disposed" && (
                <>
                  <DetailRow
                    label="Disposal date"
                    value={asset.disposal_date ? new Date(asset.disposal_date).toLocaleDateString() : "—"}
                  />
                  <DetailRow
                    label="Disposal amount"
                    value={asset.disposal_amount != null ? asset.disposal_amount.toLocaleString() : "—"}
                  />
                </>
              )}
              {asset.description && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Description</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{asset.description}</p>
                </div>
              )}
              {asset.notes && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Notes</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{asset.notes}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Net book value</CardTitle>
            </CardHeader>
            <CardContent>
              {nbv ? (
                <>
                  <DetailRow label="As of" value={new Date(nbv.as_of_date).toLocaleDateString()} />
                  <DetailRow label="Purchase cost" value={nbv.purchase_cost.toLocaleString()} />
                  <DetailRow
                    label="Accumulated depreciation"
                    value={nbv.accumulated_depreciation.toLocaleString()}
                  />
                  <DetailRow label="Net book value" value={nbv.net_book_value.toLocaleString()} />
                </>
              ) : (
                <Skeleton className="h-16 w-full" />
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <AssetEditDialog open={editOpen} onOpenChange={setEditOpen} asset={asset} />
      <DisposeAssetDialog open={disposeOpen} onOpenChange={setDisposeOpen} assetId={asset.id} />
    </div>
  );
}
