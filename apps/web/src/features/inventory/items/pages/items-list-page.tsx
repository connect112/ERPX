import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ItemFormDialog } from "@/features/inventory/items/components/item-form-dialog";
import { useItemsList } from "@/features/inventory/items/api/items-hooks";

const PAGE_SIZE = 20;

export function ItemsListPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useItemsList({
    search: search || undefined,
    skip,
    limit: PAGE_SIZE,
  });

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Inventory Items</h1>
          <p className="mt-1 text-muted-foreground">
            Manage your item catalog, stock levels, and reorder thresholds.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Item
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by SKU or name..."
              className="pl-9"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setSkip(0);
              }}
            />
          </div>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load items. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No items found. Add your first item to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>UoM</TableHead>
                  <TableHead>Reorder level</TableHead>
                  <TableHead>Standard cost</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((item) => (
                  <TableRow
                    key={item.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/inventory/items/${item.id}`)}
                  >
                    <TableCell className="font-mono text-xs text-muted-foreground">{item.sku}</TableCell>
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell className="text-muted-foreground">{item.unit_of_measure}</TableCell>
                    <TableCell className="text-muted-foreground">{item.reorder_level}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.standard_cost.toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant={item.is_active ? "success" : "secondary"}>
                        {item.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} items)
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

      <ItemFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
