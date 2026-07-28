import { ArrowLeft, ArrowRightLeft, Pencil, PlusCircle, Settings2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useItemCategories } from "@/features/inventory/categories/api/item-categories-hooks";
import { AdjustStockDialog } from "@/features/inventory/stock/components/adjust-stock-dialog";
import { IssueStockDialog } from "@/features/inventory/stock/components/issue-stock-dialog";
import { ReceiveStockDialog } from "@/features/inventory/stock/components/receive-stock-dialog";
import { StockTransactionTypeBadge } from "@/features/inventory/stock/components/stock-status-badge";
import { TransferStockDialog } from "@/features/inventory/stock/components/transfer-stock-dialog";
import { useItemTransactions } from "@/features/inventory/stock/api/stock-hooks";
import { ItemFormDialog } from "@/features/inventory/items/components/item-form-dialog";
import { useItem, useItemStockLevel } from "@/features/inventory/items/api/items-hooks";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function ItemDetailPage() {
  const { itemId } = useParams<{ itemId: string }>();
  const navigate = useNavigate();
  const { data: item, isLoading } = useItem(itemId);
  const { data: stockLevel } = useItemStockLevel(itemId);
  const { data: transactions, isLoading: transactionsLoading } = useItemTransactions(itemId, { limit: 30 });
  const { data: categories } = useItemCategories();

  const [editOpen, setEditOpen] = useState(false);
  const [receiveOpen, setReceiveOpen] = useState(false);
  const [issueOpen, setIssueOpen] = useState(false);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);

  if (isLoading || !item) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const categoryName = categories?.find((c) => c.id === item.category_id)?.name;
  const isLowStock = stockLevel != null && stockLevel.quantity_on_hand <= item.reorder_level;

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/inventory/items")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{item.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{item.sku}</span>
              <Badge variant={item.is_active ? "success" : "secondary"}>
                {item.is_active ? "Active" : "Inactive"}
              </Badge>
              {isLowStock && <Badge variant="warning">Low stock</Badge>}
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
            Edit
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Item details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Category" value={categoryName || "—"} />
              <DetailRow label="Unit of measure" value={item.unit_of_measure} />
              <DetailRow label="Reorder level" value={item.reorder_level} />
              <DetailRow label="Reorder quantity" value={item.reorder_quantity} />
              <DetailRow label="Standard cost" value={item.standard_cost.toLocaleString()} />
              {item.description && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Description</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{item.description}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Stock level</CardTitle>
            </CardHeader>
            <CardContent>
              {stockLevel ? (
                <>
                  <DetailRow label="Quantity on hand" value={stockLevel.quantity_on_hand} />
                  <DetailRow
                    label="Average unit cost"
                    value={stockLevel.average_unit_cost.toLocaleString()}
                  />
                  <DetailRow label="Stock value" value={stockLevel.stock_value.toLocaleString()} />
                </>
              ) : (
                <Skeleton className="h-16 w-full" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Stock actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button variant="outline" className="w-full justify-start" onClick={() => setReceiveOpen(true)}>
                <PlusCircle className="h-4 w-4" />
                Receive stock
              </Button>
              <Button variant="outline" className="w-full justify-start" onClick={() => setIssueOpen(true)}>
                <Settings2 className="h-4 w-4" />
                Issue stock
              </Button>
              <Button variant="outline" className="w-full justify-start" onClick={() => setAdjustOpen(true)}>
                <Settings2 className="h-4 w-4" />
                Adjust stock
              </Button>
              <Button variant="outline" className="w-full justify-start" onClick={() => setTransferOpen(true)}>
                <ArrowRightLeft className="h-4 w-4" />
                Transfer stock
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Transaction history</CardTitle>
        </CardHeader>
        <CardContent>
          {transactionsLoading && <Skeleton className="h-32 w-full" />}
          {!transactionsLoading && (transactions?.items.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No transactions yet.</p>
          )}
          {!transactionsLoading && (transactions?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Quantity</TableHead>
                  <TableHead>Unit cost</TableHead>
                  <TableHead>Notes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactions?.items.map((txn) => (
                  <TableRow key={txn.id}>
                    <TableCell className="text-muted-foreground">
                      {new Date(txn.transaction_date).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <StockTransactionTypeBadge type={txn.transaction_type} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">{txn.quantity}</TableCell>
                    <TableCell className="text-muted-foreground">{txn.unit_cost.toLocaleString()}</TableCell>
                    <TableCell className="max-w-xs truncate text-muted-foreground">
                      {txn.notes || "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ItemFormDialog open={editOpen} onOpenChange={setEditOpen} item={item} />
      <ReceiveStockDialog open={receiveOpen} onOpenChange={setReceiveOpen} defaultItemId={item.id} />
      <IssueStockDialog open={issueOpen} onOpenChange={setIssueOpen} defaultItemId={item.id} />
      <AdjustStockDialog open={adjustOpen} onOpenChange={setAdjustOpen} defaultItemId={item.id} />
      <TransferStockDialog open={transferOpen} onOpenChange={setTransferOpen} defaultItemId={item.id} />
    </div>
  );
}
