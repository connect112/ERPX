import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyContracts } from "@/features/contracts/api/contracts-hooks";

export function MyContractsPage() {
  const { data: contracts, isLoading } = useMyContracts();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">My Contracts</h1>
        <p className="text-sm text-muted-foreground">Agreements between your organization and us.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Contracts</CardTitle>
          <CardDescription>Project agreements, AMC, and retainer contracts.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : contracts && contracts.length > 0 ? (
            <ul className="divide-y">
              {contracts.map((contract) => (
                <li key={contract.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">{contract.contract_number}</p>
                    <p className="text-xs text-muted-foreground">
                      {contract.contract_type.replace("_", " ").toUpperCase()} &middot; ₹
                      {contract.contract_value.toLocaleString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className="capitalize">
                      {contract.status}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {contract.end_date
                        ? `Ends ${new Date(contract.end_date).toLocaleDateString()}`
                        : "No end date"}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No contracts on file for your organization yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
