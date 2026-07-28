import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useVendorsList } from "@/features/accounting/vendors/api/vendors-hooks";
import { usePurchaseOrdersList } from "@/features/procurement/purchase-orders/api/purchase-orders-hooks";
import { PurchaseOrderStatusBadge } from "@/features/procurement/purchase-orders/components/purchase-order-status-badge";
import {
  type PurchaseOrderStatus,
  purchaseOrderStatusLabels,
  purchaseOrderStatusValues,
} from "@/features/procurement/purchase-orders/schemas/purchase-order-schemas";

const PAGE_SIZE = 20;

export function PurchaseOrdersListPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<PurchaseOrderStatus | "all">("all");
  const [skip, setSkip] = useState(0);

  const { data, isLoading, isError } = usePurchaseOrdersList({
    status: status === "all" ? undefined : status,
    skip,
    limit: PAGE_SIZE,
  });
  const { data: vendors } = useVendorsList({ limit: 200 });
  const vendorName = (id: string) => vendors?.items.find((v) => v.id === id)?.name ?? id;

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Purchase Orders</h1>
          <p className="mt-1 text-muted-foreground">
            Create and track purchase orders through delivery and receiving.
          </p>
        </div>
        <Button onClick={() => navigate("/procurement/purchase-orders/new")}>
          <Plus className="h-4 w-4" />
          New Purchase Order
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select
            value={status}
            onValueChange={(value) => {
              setStatus(value as PurchaseOrderStatus | "all");
              setSkip(0);
            }}
          >
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {purchaseOrderStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {purchaseOrderStatusLabels[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load purchase orders. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No purchase orders found. Create your first one to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>PO number</TableHead>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Order date</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((po) => (
                  <TableRow
                    key={po.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/procurement/purchase-orders/${po.id}`)}
                  >
                    <TableCell className="font-mono text-xs text-muted-foreground">{po.po_number}</TableCell>
                    <TableCell className="font-medium">{vendorName(po.vendor_id)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(po.order_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{po.total_amount.toLocaleString()}</TableCell>
                    <TableCell>
                      <PurchaseOrderStatusBadge status={po.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} purchase orders)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip + PAGE_SIZE >= total}
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
