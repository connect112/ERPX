import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useAPAging,
  useARAging,
  useBalanceSheet,
  useProfitAndLoss,
  useTrialBalance,
} from "@/features/accounting/reports/api/reports-hooks";
import type { TrialBalanceLine, AgingBucket } from "@/features/accounting/reports/api/reports-api";

const today = () => new Date().toISOString().slice(0, 10);
const firstOfMonth = () =>
  new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10);

function LinesTable({ lines }: { lines: TrialBalanceLine[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Code</TableHead>
          <TableHead>Name</TableHead>
          <TableHead className="text-right">Debit</TableHead>
          <TableHead className="text-right">Credit</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {lines.map((line) => (
          <TableRow key={line.account_id}>
            <TableCell className="font-mono text-xs">{line.code}</TableCell>
            <TableCell>{line.name}</TableCell>
            <TableCell className="text-right">
              {line.debit_balance > 0 ? line.debit_balance.toFixed(2) : "—"}
            </TableCell>
            <TableCell className="text-right">
              {line.credit_balance > 0 ? line.credit_balance.toFixed(2) : "—"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function AgingTable({ items }: { items: AgingBucket[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Party</TableHead>
          <TableHead>Document</TableHead>
          <TableHead>Due date</TableHead>
          <TableHead className="text-right">Outstanding</TableHead>
          <TableHead>Bucket</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item, i) => (
          <TableRow key={i}>
            <TableCell className="font-medium">{item.party_name}</TableCell>
            <TableCell className="text-muted-foreground">{item.document_number}</TableCell>
            <TableCell className="text-muted-foreground">
              {new Date(item.due_date).toLocaleDateString()}
            </TableCell>
            <TableCell className="text-right">{item.outstanding_amount.toFixed(2)}</TableCell>
            <TableCell>
              <Badge variant="outline">{item.bucket}</Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function TrialBalanceTab() {
  const [asOfDate, setAsOfDate] = useState(today());
  const { data, isLoading } = useTrialBalance(asOfDate);

  return (
    <Card>
      <CardContent className="space-y-4 p-6">
        <div className="flex items-center gap-2">
          <Label htmlFor="tbDate" className="text-xs text-muted-foreground">
            As of
          </Label>
          <Input id="tbDate" type="date" className="w-48" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} />
        </div>
        {isLoading && <Skeleton className="h-64 w-full" />}
        {data && (
          <>
            <LinesTable lines={data.lines} />
            <div className="flex items-center justify-end gap-4 border-t pt-3 text-sm">
              <span>Total debit: <span className="font-medium">{data.total_debit.toFixed(2)}</span></span>
              <span>Total credit: <span className="font-medium">{data.total_credit.toFixed(2)}</span></span>
              <Badge variant={data.is_balanced ? "success" : "destructive"}>
                {data.is_balanced ? "Balanced" : "Not balanced"}
              </Badge>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ProfitAndLossTab() {
  const [periodFrom, setPeriodFrom] = useState(firstOfMonth());
  const [periodTo, setPeriodTo] = useState(today());
  const { data, isLoading } = useProfitAndLoss(periodFrom, periodTo);

  return (
    <Card>
      <CardContent className="space-y-4 p-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Label className="text-xs text-muted-foreground">From</Label>
            <Input type="date" className="w-40" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-xs text-muted-foreground">To</Label>
            <Input type="date" className="w-40" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
          </div>
        </div>
        {isLoading && <Skeleton className="h-64 w-full" />}
        {data && (
          <div className="space-y-4">
            <div>
              <p className="pb-2 text-sm font-semibold">Income</p>
              <LinesTable lines={data.income_lines} />
            </div>
            <div>
              <p className="pb-2 text-sm font-semibold">Expenses</p>
              <LinesTable lines={data.expense_lines} />
            </div>
            <div className="flex justify-end gap-4 border-t pt-3 text-sm">
              <span>Total income: <span className="font-medium">{data.total_income.toFixed(2)}</span></span>
              <span>Total expense: <span className="font-medium">{data.total_expense.toFixed(2)}</span></span>
              <span className="text-base font-semibold">Net profit: {data.net_profit.toFixed(2)}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function BalanceSheetTab() {
  const [asOfDate, setAsOfDate] = useState(today());
  const { data, isLoading } = useBalanceSheet(asOfDate);

  return (
    <Card>
      <CardContent className="space-y-4 p-6">
        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground">As of</Label>
          <Input type="date" className="w-48" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} />
        </div>
        {isLoading && <Skeleton className="h-64 w-full" />}
        {data && (
          <div className="space-y-4">
            <div>
              <p className="pb-2 text-sm font-semibold">Assets</p>
              <LinesTable lines={data.asset_lines} />
            </div>
            <div>
              <p className="pb-2 text-sm font-semibold">Liabilities</p>
              <LinesTable lines={data.liability_lines} />
            </div>
            <div>
              <p className="pb-2 text-sm font-semibold">Equity</p>
              <LinesTable lines={data.equity_lines} />
            </div>
            <div className="grid grid-cols-2 gap-2 border-t pt-3 text-sm">
              <span>Total assets: <span className="font-medium">{data.total_assets.toFixed(2)}</span></span>
              <span>Total liabilities: <span className="font-medium">{data.total_liabilities.toFixed(2)}</span></span>
              <span>Total equity: <span className="font-medium">{data.total_equity.toFixed(2)}</span></span>
              <span>Retained earnings: <span className="font-medium">{data.retained_earnings.toFixed(2)}</span></span>
              <span>Liabilities + equity: <span className="font-medium">{data.total_liabilities_and_equity.toFixed(2)}</span></span>
              <Badge variant={data.is_balanced ? "success" : "destructive"} className="w-fit">
                {data.is_balanced ? "Balanced" : "Not balanced"}
              </Badge>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AgingTab({ type }: { type: "receivables" | "payables" }) {
  const [asOfDate, setAsOfDate] = useState(today());
  const receivables = useARAging(type === "receivables" ? asOfDate : "");
  const payables = useAPAging(type === "payables" ? asOfDate : "");
  const { data, isLoading } = type === "receivables" ? receivables : payables;

  return (
    <Card>
      <CardContent className="space-y-4 p-6">
        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground">As of</Label>
          <Input type="date" className="w-48" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} />
        </div>
        {isLoading && <Skeleton className="h-64 w-full" />}
        {data && (
          <>
            {data.items.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">Nothing outstanding.</p>
            ) : (
              <AgingTable items={data.items} />
            )}
            <div className="flex flex-wrap items-center justify-end gap-3 border-t pt-3 text-sm">
              {Object.entries(data.bucket_totals).map(([bucket, total]) => (
                <span key={bucket} className="text-muted-foreground">
                  {bucket}: <span className="font-medium text-foreground">{total.toFixed(2)}</span>
                </span>
              ))}
              <span className="text-base font-semibold">
                Total: {data.total_outstanding.toFixed(2)}
              </span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function ReportsPage() {
  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Financial Reports</h1>
        <p className="mt-1 text-muted-foreground">
          Trial balance, profit and loss, balance sheet, and aging reports — all computed live from the ledger.
        </p>
      </div>

      <Tabs defaultValue="trial-balance">
        <div className="overflow-x-auto">
          <TabsList>
            <TabsTrigger value="trial-balance">Trial Balance</TabsTrigger>
            <TabsTrigger value="pnl">Profit &amp; Loss</TabsTrigger>
            <TabsTrigger value="balance-sheet">Balance Sheet</TabsTrigger>
            <TabsTrigger value="ar-aging">AR Aging</TabsTrigger>
            <TabsTrigger value="ap-aging">AP Aging</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="trial-balance">
          <TrialBalanceTab />
        </TabsContent>
        <TabsContent value="pnl">
          <ProfitAndLossTab />
        </TabsContent>
        <TabsContent value="balance-sheet">
          <BalanceSheetTab />
        </TabsContent>
        <TabsContent value="ar-aging">
          <AgingTab type="receivables" />
        </TabsContent>
        <TabsContent value="ap-aging">
          <AgingTab type="payables" />
        </TabsContent>
      </Tabs>
    </div>
  );
}
