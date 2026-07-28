import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";

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
import type { CustomerPublic } from "@/features/accounting/customers/api/customers-api";
import { useCustomersList, useDeleteCustomer } from "@/features/accounting/customers/api/customers-hooks";
import { CustomerFormDialog } from "@/features/accounting/customers/pages/customer-form-dialog";
import { customerTypeLabels } from "@/features/accounting/customers/schemas/customer-schemas";

export function CustomersListPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading, isError } = useCustomersList({ search: search || undefined, limit: 200 });
  const deleteCustomer = useDeleteCustomer();

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<CustomerPublic | undefined>(undefined);

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Customers</h1>
          <p className="mt-1 text-muted-foreground">
            Billing parties invoices and receipts are issued against.
          </p>
        </div>
        <Button
          onClick={() => {
            setEditing(undefined);
            setFormOpen(true);
          }}
        >
          <Plus className="h-4 w-4" />
          New Customer
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <div className="relative sm:w-72">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search customers..."
              className="pl-9"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load customers.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No customers yet.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((customer) => (
                  <TableRow key={customer.id}>
                    <TableCell className="font-mono text-xs">{customer.customer_code}</TableCell>
                    <TableCell className="font-medium">{customer.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {customerTypeLabels[customer.customer_type]}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {customer.email || customer.phone || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={customer.is_active ? "success" : "secondary"}>
                        {customer.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setEditing(customer);
                            setFormOpen(true);
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => deleteCustomer.mutate(customer.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <CustomerFormDialog open={formOpen} onOpenChange={setFormOpen} customer={editing} />
    </div>
  );
}
