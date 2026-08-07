"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { FileText, Download, Loader2, CircleDollarSign, Zap, Repeat, BrainCircuit } from "lucide-react";
import { api, type Payouts, type FlowPatterns, type MlOutliers } from "@/lib/api";
import { toast } from "sonner";

function fmtAmount(n: number) {
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export function ReportsSection() {
  const [payouts, setPayouts] = useState<Payouts | null>(null);
  const [flows, setFlows] = useState<FlowPatterns | null>(null);
  const [outliers, setOutliers] = useState<MlOutliers | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    Promise.all([api.payouts(), api.flowPatterns(10000), api.mlOutliers(0.05)])
      .then(([p, f, o]) => {
        setPayouts(p);
        setFlows(f);
        setOutliers(o);
      })
      .catch((e) => toast.error(e.status === 409 ? "No data loaded." : "Failed to load reports."))
      .finally(() => setLoading(false));
  }, []);

  const downloadSTR = async () => {
    setDownloading(true);
    try {
      await api.downloadReport();
    } catch (e) {
      toast.error((e as { message?: string })?.message ?? "Failed to generate STR PDF.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card className="border-emerald-500/30">
        <CardHeader className="flex flex-row items-center gap-2 flex-wrap">
          <FileText className="h-5 w-5 text-emerald-500" />
          <div>
            <CardTitle>Suspicious Transaction Report (STR)</CardTitle>
            <CardDescription>
              Official STR PDF generated from the fused bank + CDR + NCRP evidence.
            </CardDescription>
          </div>
          <div className="ml-auto">
            <Button
              onClick={downloadSTR}
              disabled={downloading}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {downloading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  GENERATING...
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  DOWNLOAD STR PDF
                </>
              )}
            </Button>
          </div>
        </CardHeader>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center gap-2">
            <CircleDollarSign className="h-5 w-5 text-red-500" />
            <CardTitle>Round-Trip Payouts</CardTitle>
            <CardDescription>Debit amounts in round lakh groupings — cash-out signature</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[420px]">
              {loading ? (
                <div className="p-8 text-center text-muted-foreground animate-pulse">Loading...</div>
              ) : !payouts || payouts.round.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">No round payouts detected.</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                    <tr>
                      <th className="p-3 text-left font-medium">Account</th>
                      <th className="p-3 text-left font-medium">Date</th>
                      <th className="p-3 text-right font-medium">Amount</th>
                      <th className="p-3 text-left font-medium">Mode</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payouts.round.slice(0, 50).map((p, i) => (
                      <tr key={i} className="border-b border-border/50">
                        <td className="p-3 font-mono text-xs">{p.account_no}</td>
                        <td className="p-3 text-xs">{p.date}</td>
                        <td className="p-3 font-mono text-right text-red-500">{fmtAmount(p.amount || 0)}</td>
                        <td className="p-3 text-xs">
                          <Badge variant="outline">{p.mode || "—"}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center gap-2">
            <Zap className="h-5 w-5 text-amber-500" />
            <CardTitle>Rapid Payout Windows</CardTitle>
            <CardDescription>Accounts draining via ≥5 debits within 60 minutes</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[420px]">
              {loading ? (
                <div className="p-8 text-center text-muted-foreground animate-pulse">Loading...</div>
              ) : !payouts || payouts.rapid.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">No rapid payout windows detected.</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                    <tr>
                      <th className="p-3 text-left font-medium">Account</th>
                      <th className="p-3 text-right font-medium">Debits</th>
                      <th className="p-3 text-right font-medium">Window</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payouts.rapid.slice(0, 50).map((p, i) => (
                      <tr key={i} className="border-b border-border/50">
                        <td className="p-3 font-mono text-xs">{p.account_no}</td>
                        <td className="p-3 text-right font-bold text-amber-500">{p.count}</td>
                        <td className="p-3 text-right text-xs">{p.window_min} min</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center gap-2">
            <Repeat className="h-5 w-5 text-violet-500" />
            <CardTitle>Circular Flows &amp; Rapid In-Out</CardTitle>
            <CardDescription>Money loops between accounts + cash-through windows (rules engine)</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[420px]">
              {loading ? (
                <div className="p-8 text-center text-muted-foreground animate-pulse">Loading...</div>
              ) : !flows || (flows.circular.length === 0 && flows.rapid_in_out.length === 0) ? (
                <div className="p-8 text-center text-muted-foreground">No circular flows or rapid in-out detected.</div>
              ) : (
                <div className="divide-y divide-border/50">
                  {flows?.circular.map((c, i) => (
                    <div key={`c${i}`} className="p-3">
                      <p className="text-xs font-mono text-violet-500">
                        {c.accounts.join(" → ")}{" "}
                        <span className="text-muted-foreground">(cycle of {c.length})</span>
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Total flow {fmtAmount(c.total_flow)} · weakest leg {fmtAmount(c.min_leg)}
                      </p>
                    </div>
                  ))}
                  {flows?.rapid_in_out.map((r, i) => (
                    <div key={`r${i}`} className="p-3">
                      <p className="text-xs font-mono text-amber-500">
                        {r.account_no}
                        <span className="text-muted-foreground"> — in Rs {r.in_amount} → out Rs {r.out_amount}</span>
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        In-and-out within {r.window_min} min · mode {r.mode || "—"} · {r.in_txn} / {r.out_txn}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center gap-2">
            <BrainCircuit className="h-5 w-5 text-cyan-500" />
            <CardTitle>ML Outlier Accounts</CardTitle>
            <CardDescription>IsolationForest + z-score anomalies over behavioural features</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[420px]">
              {loading ? (
                <div className="p-8 text-center text-muted-foreground animate-pulse">Loading...</div>
              ) : !outliers || !outliers.fitted || outliers.accounts.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">
                  {outliers && !outliers.fitted
                    ? "Not enough accounts (≥8 with 5+ txns) to fit the model."
                    : "No statistical outliers detected."}
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                    <tr>
                      <th className="p-3 text-left font-medium">Account</th>
                      <th className="p-3 text-right font-medium">Txns</th>
                      <th className="p-3 text-right font-medium">Max txn</th>
                      <th className="p-3 text-right font-medium">Parties</th>
                      <th className="p-3 text-right font-medium">Round%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {outliers.accounts.slice(0, 50).map((a, i) => (
                      <tr key={i} className="border-b border-border/50">
                        <td className="p-3 font-mono text-xs text-cyan-500">{a.account_no}</td>
                        <td className="p-3 text-right text-xs">{a.txn_count}</td>
                        <td className="p-3 font-mono text-right text-red-500">{fmtAmount(a.max_amount)}</td>
                        <td className="p-3 text-right text-xs">{a.counterparties}</td>
                        <td className="p-3 text-right text-xs">{Math.round(a.round_share * 100)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
