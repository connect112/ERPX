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
import { useVendorsList } from "@/features/accounting/vendors/api/vendors-hooks";
import { VendorFormDialog } from "@/features/accounting/vendors/pages/vendor-form-dialog";

export function VendorsListPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const { data, isLoading, isError } = useVendorsList({ search: search || undefined, limit: 200 });
  const [formOpen, setFormOpen] = useState(false);

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Vendors</h1>
          <p className="mt-1 text-muted-foreground">Suppliers expenses and payments are made to.</p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Vendor
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <div className="relative sm:w-72">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search vendors..."
              className="pl-9"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load vendors.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No vendors yet.</p>
          )}
          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>GSTIN</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((vendor) => (
                  <TableRow
                    key={vendor.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/accounting/vendors/${vendor.id}`)}
                  >
                    <TableCell className="font-mono text-xs">{vendor.vendor_code}</TableCell>
                    <TableCell className="font-medium">{vendor.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {vendor.email || vendor.phone || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{vendor.gstin || "—"}</TableCell>
                    <TableCell>
                      <Badge variant={vendor.is_active ? "success" : "secondary"}>
                        {vendor.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <VendorFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
