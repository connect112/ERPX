import { zodResolver } from "@hookform/resolvers/zod";
import { Calculator, Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useComputeTax, useCreateGSTRate, useGSTRates, useGSTReturnSummary } from "@/features/accounting/gst/api/gst-hooks";
import { type GSTRateFormValues, gstRateFormSchema } from "@/features/accounting/gst/schemas/gst-schemas";

function TaxCalculatorCard() {
  const { data: rates } = useGSTRates(true);
  const computeTax = useComputeTax();
  const [amount, setAmount] = useState("");
  const [rateId, setRateId] = useState("");
  const [interstate, setInterstate] = useState(false);

  const onCompute = () => {
    if (!amount || !rateId) return;
    computeTax.mutate({ taxableAmount: Number(amount), gstRateId: rateId, isInterstate: interstate });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Tax calculator</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="taxableAmount">Taxable amount</Label>
            <Input id="taxableAmount" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="rateId">GST rate</Label>
            <Select value={rateId || undefined} onValueChange={setRateId}>
              <SelectTrigger id="rateId">
                <SelectValue placeholder="Select rate" />
              </SelectTrigger>
              <SelectContent>
                {rates?.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.name} ({r.rate_percent}%)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-input"
            checked={interstate}
            onChange={(e) => setInterstate(e.target.checked)}
          />
          Interstate transaction (IGST instead of CGST+SGST)
        </label>
        <Button onClick={onCompute} disabled={!amount || !rateId || computeTax.isPending}>
          <Calculator className="h-4 w-4" />
          {computeTax.isPending ? "Computing..." : "Compute"}
        </Button>
        {computeTax.data && (
          <div className="grid grid-cols-2 gap-2 rounded-md border p-3 text-sm">
            {computeTax.data.is_interstate ? (
              <div>
                <p className="text-muted-foreground">IGST</p>
                <p className="font-medium">₹{computeTax.data.igst_amount.toFixed(2)}</p>
              </div>
            ) : (
              <>
                <div>
                  <p className="text-muted-foreground">CGST</p>
                  <p className="font-medium">₹{computeTax.data.cgst_amount.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">SGST</p>
                  <p className="font-medium">₹{computeTax.data.sgst_amount.toFixed(2)}</p>
                </div>
              </>
            )}
            <div>
              <p className="text-muted-foreground">Total tax</p>
              <p className="font-medium">₹{computeTax.data.total_tax.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Total amount</p>
              <p className="font-semibold">₹{computeTax.data.total_amount.toFixed(2)}</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ReturnSummaryCard() {
  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1)
    .toISOString()
    .slice(0, 10);
  const [periodFrom, setPeriodFrom] = useState(firstOfMonth);
  const [periodTo, setPeriodTo] = useState(today);
  const { data: summary, isLoading } = useGSTReturnSummary(periodFrom, periodTo, true);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Return summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="periodFrom">From</Label>
            <Input id="periodFrom" type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="periodTo">To</Label>
            <Input id="periodTo" type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
          </div>
        </div>
        {isLoading && <Skeleton className="h-24 w-full" />}
        {summary && (
          <div className="grid grid-cols-2 gap-3 rounded-md border p-3 text-sm">
            <div>
              <p className="text-muted-foreground">Output taxable value</p>
              <p className="font-medium">₹{summary.output_taxable_value.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Output tax collected</p>
              <p className="font-medium">₹{summary.output_tax_collected.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Input taxable value</p>
              <p className="font-medium">₹{summary.input_taxable_value.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Input tax credit</p>
              <p className="font-medium">₹{summary.input_tax_credit.toFixed(2)}</p>
            </div>
            <div className="col-span-2 border-t pt-2">
              <p className="text-muted-foreground">Net tax payable</p>
              <p className="text-base font-semibold">₹{summary.net_tax_payable.toFixed(2)}</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function GSTPage() {
  const { data: rates, isLoading, isError } = useGSTRates();
  const createRate = useCreateGSTRate();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<GSTRateFormValues>({ resolver: zodResolver(gstRateFormSchema) });

  const onSubmit = (values: GSTRateFormValues) => {
    createRate.mutate(
      { name: values.name, rate_percent: Number(values.ratePercent), hsn_sac_code: values.hsnSacCode || undefined },
      {
        onSuccess: () => {
          setFormOpen(false);
          reset();
        },
      }
    );
  };

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">GST</h1>
        <p className="mt-1 text-muted-foreground">Tax rates, computation, and return summaries.</p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">GST rates</CardTitle>
          <Button size="sm" onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" />
            New rate
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {isLoading && <Skeleton className="h-16 w-full" />}
          {isError && <p className="text-sm text-destructive">Failed to load GST rates.</p>}
          {!isLoading && !isError && (rates?.length ?? 0) === 0 && (
            <p className="text-sm text-muted-foreground">No GST rates configured yet.</p>
          )}
          {rates?.map((rate) => (
            <div key={rate.id} className="flex items-center justify-between rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">
                  {rate.name} — {rate.rate_percent}%
                </p>
                {rate.hsn_sac_code && (
                  <p className="text-xs text-muted-foreground">HSN/SAC: {rate.hsn_sac_code}</p>
                )}
              </div>
              <Badge variant={rate.is_active ? "success" : "secondary"}>
                {rate.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <TaxCalculatorCard />
        <ReturnSummaryCard />
      </div>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New GST rate</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" placeholder="e.g. GST 18%" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ratePercent">Rate %</Label>
                <Input id="ratePercent" type="number" step="0.01" {...register("ratePercent")} />
                {errors.ratePercent && (
                  <p className="text-sm text-destructive">{errors.ratePercent.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="hsnSacCode">HSN/SAC code</Label>
                <Input id="hsnSacCode" {...register("hsnSacCode")} />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createRate.isPending}>
                {createRate.isPending ? "Saving..." : "Create rate"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
