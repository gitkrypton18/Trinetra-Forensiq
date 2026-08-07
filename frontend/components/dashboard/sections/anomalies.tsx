"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  ShieldAlert, AlertTriangle, FileText, Activity, ShieldCheck,
  Database, Search, Download, PhoneCall, Globe, Gavel,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { api, type Alert, type FusedRow } from "@/lib/api";

const PAGE_SIZE = 25;

const fmtTs = (ts: number | null | undefined): string => {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

export function AnomaliesSection() {
  const [stage, setStage] = useState<"fused" | "alerts">("fused");

  // --- Fused records stage ---
  const [rows, setRows] = useState<FusedRow[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [q, setQ] = useState("");
  const [account, setAccount] = useState("");
  const [riskAnnotate, setRiskAnnotate] = useState(false);
  const [fusedLoading, setFusedLoading] = useState(true);
  const [selectedRow, setSelectedRow] = useState<FusedRow | null>(null);
  const [fusedKey, setFusedKey] = useState(0);

  // --- Alerts stage ---
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  const loadFused = useCallback(() => {
    setFusedLoading(true);
    api
      .fused(offset, PAGE_SIZE, q, account, riskAnnotate)
      .then((res) => {
        setRows(res.rows || []);
        setTotal(res.total ?? 0);
      })
      .catch((error) => {
        const err = error as { status?: number };
        toast.error(err.status === 409
          ? "No data fused yet. Run the ingestion pipeline first."
          : "Failed to load fused records. Is the backend running?");
        setRows([]);
        setTotal(0);
      })
      .finally(() => setFusedLoading(false));
  }, [offset, q, account, riskAnnotate]);

  useEffect(() => {
    loadFused();
  }, [loadFused, fusedKey]);

  const showAnomalies = async () => {
    setAlertsLoading(true);
    setStage("alerts");
    try {
      const res = await api.alerts(50);
      setAlerts(res.results || []);
    } catch (error) {
      const err = error as { status?: number };
      toast.error(err.status === 409
        ? "No data fused yet. Run the ingestion pipeline first."
        : "Failed to load anomalies. Is the backend running?");
    } finally {
      setAlertsLoading(false);
    }
  };

  const downloadFusedCsv = async () => {
    try {
      await api.fusedCsv(q, account);
      toast.success("Fused records CSV export started.");
    } catch (e) {
      toast.error((e as { message?: string })?.message ?? "Failed to export CSV.");
    }
  };

  const downloadSTR = async () => {
    try {
      await api.downloadReport();
    } catch (e) {
      toast.error((e as { message?: string })?.message ?? "Failed to generate STR PDF.");
    }
  };

  const rules = selectedAlert
    ? selectedAlert.rules_fired.replace(/[\[\]']/g, "").split(",").map((r) => r.trim()).filter(Boolean)
    : [];

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const page = Math.floor(offset / PAGE_SIZE) + 1;

  if (stage === "fused") {
    return (
      <div className="space-y-6 h-[calc(100vh-12rem)]">
        <Card className="flex flex-col h-full">
          <CardHeader className="flex flex-row flex-wrap items-center gap-2 border-b border-border">
            <Database className="h-6 w-6 text-cyan-500" />
            <div className="flex-1 min-w-[220px]">
              <CardTitle className="text-cyan-500">Fused Records</CardTitle>
              <CardDescription>
                {total.toLocaleString()} bank transactions fused with CDR calls, IPDR sessions & NCRP complaints
              </CardDescription>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Switch
                  id="risk-annotate"
                  checked={riskAnnotate}
                  onCheckedChange={(v) => { setRiskAnnotate(v); setOffset(0); }}
                />
                <label htmlFor="risk-annotate">Risk annotation</label>
              </div>
              <Button variant="outline" size="sm" onClick={downloadFusedCsv}>
                <Download className="h-4 w-4 mr-1" /> CSV
              </Button>
              <Button
                size="sm"
                className="bg-red-600 hover:bg-red-700 text-white"
                onClick={showAnomalies}
                disabled={alertsLoading}
              >
                <ShieldAlert className="h-4 w-4 mr-1" />
                {alertsLoading ? "Loading..." : "Show Anomalies"}
              </Button>
            </div>
          </CardHeader>

          <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-8"
                placeholder="Search transaction id, account, customer, phone..."
                value={q}
                onChange={(e) => { setQ(e.target.value); setOffset(0); }}
              />
            </div>
            <Input
              className="w-44"
              placeholder="Account filter"
              value={account}
              onChange={(e) => { setAccount(e.target.value); setOffset(0); }}
            />
            <Button
              size="sm"
              variant="secondary"
              onClick={() => { setOffset(0); setFusedKey((k) => k + 1); }}
            >
              Apply
            </Button>
          </div>

          <CardContent className="p-0 flex-1 overflow-hidden">
            <ScrollArea className="h-full">
              {fusedLoading ? (
                <div className="p-8 text-center text-muted-foreground animate-pulse">Loading fused records...</div>
              ) : rows.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">
                  No fused records. Ingest bank + CDR + IPDR datasets first.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                    <tr>
                      <th className="p-3 text-left font-medium">Date/Time</th>
                      <th className="p-3 text-left font-medium">Sender</th>
                      <th className="p-3 text-left font-medium">Receiver</th>
                      <th className="p-3 text-left font-medium">Amount</th>
                      <th className="p-3 text-left font-medium">Mode</th>
                      <th className="p-3 text-center font-medium">Calls</th>
                      <th className="p-3 text-center font-medium">IPDR</th>
                      <th className="p-3 text-center font-medium">NCRP</th>
                      {riskAnnotate && <th className="p-3 text-left font-medium">Risk</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, idx) => (
                      <motion.tr
                        key={row.transaction_id + idx}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(idx, 10) * 0.03 }}
                        onClick={() => setSelectedRow(selectedRow?.transaction_id === row.transaction_id ? null : row)}
                        className={`cursor-pointer transition-colors hover:bg-muted/30 border-b border-border/50 ${
                          selectedRow?.transaction_id === row.transaction_id ? "bg-cyan-950/20" : ""
                        }`}
                      >
                        <td className="p-3 whitespace-nowrap font-mono text-xs">{row.date} {row.time}</td>
                        <td className="p-3">
                          <div className="font-mono text-xs">{row.account_no}</div>
                          <div className="text-xs text-muted-foreground">{row.account_name || row.sender_phone}</div>
                        </td>
                        <td className="p-3">
                          <div className="font-mono text-xs">{row.receiver_account}</div>
                          <div className="text-xs text-muted-foreground">{row.counterparty_name || row.receiver_phone}</div>
                        </td>
                        <td className="p-3 font-mono">₹{Number(row.amount || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}</td>
                        <td className="p-3"><Badge variant="outline">{row.mode}</Badge></td>
                        <td className="p-3 text-center">
                          {row.call_count ? (
                            <Badge className="bg-cyan-500/10 text-cyan-400 border-cyan-500/40">{row.call_count}</Badge>
                          ) : (
                            <span className="text-muted-foreground/40">-</span>
                          )}
                        </td>
                        <td className="p-3 text-center">
                          {row.ipdr_count ? (
                            <Badge className="bg-violet-500/10 text-violet-400 border-violet-500/40">{row.ipdr_count}</Badge>
                          ) : (
                            <span className="text-muted-foreground/40">-</span>
                          )}
                        </td>
                        <td className="p-3 text-center">
                          {row.ncrp ? (
                            <Badge className="bg-amber-500/10 text-amber-400 border-amber-500/40"><Gavel className="h-3 w-3 mr-1" />NCRP</Badge>
                          ) : (
                            <span className="text-muted-foreground/40">-</span>
                          )}
                        </td>
                        {riskAnnotate && (
                          <td className="p-3">
                            {typeof row.risk_score === "number" ? (
                              <div>
                                <span className="font-bold text-red-500">{row.risk_score.toFixed(1)}</span>
                                <span className="text-xs text-muted-foreground ml-2">{row.risk_band}</span>
                              </div>
                            ) : (
                              <span className="text-muted-foreground/40">-</span>
                            )}
                          </td>
                        )}
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              )}
            </ScrollArea>
          </CardContent>

          {selectedRow && (
            <div className="border-t border-border p-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="lg:col-span-2 flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-muted-foreground">{selectedRow.transaction_id}</span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => api.transactionReport(selectedRow.transaction_id).catch((e) => toast.error((e as { message?: string })?.message ?? "Failed to export STR PDF."))}
                >
                  <FileText className="h-4 w-4 mr-1" /> Transaction STR
                </Button>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2 flex items-center gap-1.5">
                  <PhoneCall className="h-3.5 w-3.5 text-cyan-500" /> Linked Calls ({selectedRow.linked_calls?.length ?? 0})
                </div>
                {!selectedRow.linked_calls?.length ? (
                  <p className="text-sm text-muted-foreground/50">No CDR call within the correlation window.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {selectedRow.linked_calls.map((c) => (
                      <li key={c.cdr_id} className="text-xs bg-muted/30 rounded p-2 font-mono">
                        {c.cdr_id} · {fmtTs(c.ts)} · {c.type} · {c.dur}s · {c.phone}
                        <span className="text-muted-foreground"> @ {c.bts}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2 flex items-center gap-1.5">
                  <Globe className="h-3.5 w-3.5 text-violet-500" /> Linked IP Sessions ({selectedRow.linked_sessions?.length ?? 0})
                </div>
                {!selectedRow.linked_sessions?.length ? (
                  <p className="text-sm text-muted-foreground/50">No IPDR session within the correlation window.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {selectedRow.linked_sessions.map((s) => (
                      <li key={s.ipdr_id} className="text-xs bg-muted/30 rounded p-2 font-mono">
                        {s.ipdr_id} · {fmtTs(s.ts)} · {s.ip}
                        <span className="text-muted-foreground"> · {s.dur}s</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          <div className="flex items-center justify-between p-3 border-t border-border text-sm">
            <span className="text-muted-foreground">
              Page {page} of {pages} · {total.toLocaleString()} records
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-12rem)]">
      <Card className="lg:col-span-2 flex flex-col">
        <CardHeader className="flex flex-row items-center gap-2 border-b border-border">
          <ShieldAlert className="h-6 w-6 text-red-500" />
          <div className="flex-1">
            <CardTitle className="text-red-500">Anomaly Detection Feed</CardTitle>
            <CardDescription>Highest risk transactions flagged by Behavioral Scoring Engine</CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => setStage("fused")}>
            <Database className="h-4 w-4 mr-1" /> Back to Fused Records
          </Button>
        </CardHeader>
        <CardContent className="p-0 flex-1 overflow-hidden">
          <ScrollArea className="h-full">
            {alertsLoading ? (
              <div className="p-8 text-center text-muted-foreground animate-pulse">Loading alerts...</div>
            ) : alerts.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                No anomalies above risk 50 found. Have you fused the datasets?
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                  <tr>
                    <th className="p-3 text-left font-medium">Txn ID</th>
                    <th className="p-3 text-left font-medium">Entity</th>
                    <th className="p-3 text-left font-medium">Amount</th>
                    <th className="p-3 text-left font-medium">Risk Score</th>
                    <th className="p-3 text-left font-medium">Band</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((alert, idx) => (
                    <motion.tr
                      key={idx}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.05 }}
                      onClick={() => setSelectedAlert(alert)}
                      className={`cursor-pointer transition-colors hover:bg-muted/30 border-b border-border/50 ${selectedAlert?.transaction_id === alert.transaction_id ? 'bg-red-950/20' : ''}`}
                    >
                      <td className="p-3 font-mono text-xs">{(alert.transaction_id || "").substring(0, 8)}...</td>
                      <td className="p-3">{alert.sender_customer_id}</td>
                      <td className="p-3 font-mono">₹{alert.amount_usd.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</td>
                      <td className="p-3 font-bold text-red-500">{alert.risk_score.toFixed(1)}</td>
                      <td className="p-3">
                        <Badge variant="outline" className="text-red-500 border-red-500/50 bg-red-500/10">
                          {alert.risk_band}
                        </Badge>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            )}
          </ScrollArea>
        </CardContent>
      </Card>

      <div className="space-y-6 flex flex-col h-full">
        <Card className="flex-1 overflow-hidden flex flex-col">
          <CardHeader className="border-b border-border bg-muted/20 pb-4">
            <CardTitle className="text-sm flex items-center gap-2 text-emerald-500">
              <Activity className="h-4 w-4" />
              Transaction Explainability
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 flex-1 overflow-auto">
            {!selectedAlert ? (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground/50 text-center">
                <AlertTriangle className="h-10 w-10 mb-2" />
                <p>Select a transaction from the feed to view AI rationale</p>
              </div>
            ) : (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                <div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider font-semibold mb-1">Account</div>
                  <div className="font-mono text-sm break-all bg-muted/30 p-2 rounded">{selectedAlert.sender_customer_id}</div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider font-semibold mb-1">Risk Score</div>
                    <div className="text-3xl font-black text-red-500">{selectedAlert.risk_score.toFixed(1)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider font-semibold mb-1">Band</div>
                    <Badge className="bg-red-500 hover:bg-red-600">{selectedAlert.risk_band}</Badge>
                  </div>
                </div>

                <div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider font-semibold mb-1">AI Rationale (Rules Fired)</div>
                  <ul className="space-y-2 mt-2">
                    {rules.length === 0 && <li className="text-sm text-muted-foreground">No rules fired.</li>}
                    {rules.map((rule: string, i: number) => (
                      <li key={i} className="text-sm bg-red-950/20 text-red-400 p-2 rounded border border-red-500/20 flex items-start gap-2">
                        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                        <span>{rule}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </motion.div>
            )}
          </CardContent>
        </Card>

        <Card className="h-1/3 min-h-[200px]">
          <CardHeader className="border-b border-border bg-muted/20 py-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <FileText className="h-4 w-4" />
              STR Generation
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 flex flex-col items-center justify-center text-center h-full">
            {selectedAlert ? (
              <>
                <ShieldCheck className="h-10 w-10 text-emerald-500 mb-3" />
                <p className="text-sm text-muted-foreground mb-4">
                  Generate an official Suspicious Transaction Report for entity{" "}
                  <b>{selectedAlert.sender_customer_id}</b>.
                </p>
                <Button onClick={downloadSTR} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white holographic-border">
                  GENERATE STR PDF
                </Button>
              </>
            ) : (
              <p className="text-sm text-muted-foreground/50">Select a transaction first</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
