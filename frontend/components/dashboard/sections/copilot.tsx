"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Bot, User, Send, Brain, Database, Network, FileCode2, Lightbulb,
  ChevronDown, ChevronRight, PhoneCall, Coins, Landmark, CreditCard,
  Globe, Hash, User as UserIcon, Gavel, Cloud, TowerControl, FileWarning,
  Download, Sparkles, Compass, ShieldAlert, Clock, Target, ArrowRight,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { api, type CopilotQueryResult, type CopilotRecord } from "@/lib/api";

interface ChatMessage {
  role: "user" | "copilot";
  query?: string;
  result?: CopilotQueryResult;
  error?: string;
}

const SUGGESTIONS = [
  "Trace the 3-hop mule money flow from 1001",
  "Show NCRP complaints for account 1001",
  "Who are the top receivers showing layering?",
  "Show UPI transactions greater than 15000",
  "Trace all activity for phone 9160000001",
];

const RISK_BAND_CLS: Record<string, string> = {
  LOW: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  MEDIUM: "text-cyan-400 border-cyan-500/30 bg-cyan-500/10",
  HIGH: "text-yellow-400 border-yellow-500/30 bg-yellow-500/10",
  CRITICAL: "text-orange-400 border-orange-500/30 bg-orange-500/10",
  SEVERE: "text-red-400 border-red-500/30 bg-red-500/10",
};

const ROW_BAND_CLS: Record<string, string> = {
  LOW: "border-l-emerald-500/60",
  MEDIUM: "border-l-cyan-500/60",
  HIGH: "border-l-yellow-500/60",
  CRITICAL: "border-l-orange-500/60",
  SEVERE: "border-l-red-500/60",
};

const INSIGHT_CLS: Record<string, string> = {
  low: "border-emerald-500/25 text-emerald-400",
  medium: "border-yellow-500/25 text-yellow-400",
  high: "border-red-500/25 text-red-400",
};

const ENTITY_TYPE_META: Record<string, { icon: React.ElementType; cls: string; label: string }> = {
  transaction: { icon: CreditCard, cls: "text-cyan-400 border-cyan-500/30", label: "Transaction" },
  account: { icon: Landmark, cls: "text-sky-400 border-sky-500/30", label: "Account" },
  phone: { icon: PhoneCall, cls: "text-emerald-400 border-emerald-500/30", label: "Phone" },
  customer: { icon: UserIcon, cls: "text-lime-400 border-lime-500/30", label: "Customer" },
  imei: { icon: Hash, cls: "text-fuchsia-400 border-fuchsia-500/30", label: "IMEI" },
  imsi: { icon: Hash, cls: "text-fuchsia-400 border-fuchsia-500/30", label: "IMSI" },
  ip: { icon: Globe, cls: "text-violet-400 border-violet-500/30", label: "IP" },
  beneficiary: { icon: Target, cls: "text-purple-400 border-purple-500/30", label: "Beneficiary" },
  tower: { icon: TowerControl, cls: "text-blue-400 border-blue-500/30", label: "Tower" },
  upi: { icon: Sparkles, cls: "text-rose-400 border-rose-500/30", label: "UPI" },
  complaint: { icon: FileWarning, cls: "text-red-400 border-red-500/30", label: "Complaint" },
  call: { icon: PhoneCall, cls: "text-cyan-400 border-cyan-500/30", label: "Call" },
  session: { icon: Cloud, cls: "text-emerald-400 border-emerald-500/30", label: "Session" },
  identifier: { icon: Compass, cls: "text-muted-foreground border-border", label: "Identifier" },
};

const fmtINR = (n: number | null | undefined) =>
  n == null ? "—" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

const fmtDate = (v: string | number | null) => {
  if (v == null || v === "") return "";
  const s = String(v);
  if (/^\d{10}$/.test(s)) return new Date(Number(s) * 1000).toISOString().slice(0, 19).replace("T", " ");
  return s.slice(0, 19).replace("T", " ");
};

function isEntityKey(key: string): boolean {
  return /(transaction_id|account|customer|phone|msisdn|imei|imsi|ip_address|^ip$|upi|beneficiary)/i.test(key);
}

function csvFromRecords(records: CopilotRecord[]): string {
  if (!records.length) return "";
  const cols = Object.keys(records[0]);
  const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return [cols.join(","), ...records.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
}

export function CopilotSection() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [treeOpen, setTreeOpen] = useState<Record<string, boolean>>({});
  const [explainOpen, setExplainOpen] = useState<Record<string, boolean>>({});
  const [tab, setTab] = useState<Record<string, "evidence" | "timeline" | "graph" | "sql">>({});
  const [sortDir, setSortDir] = useState<Record<string, "asc" | "desc">>({});
  const [treeNodeOpen, setTreeNodeOpen] = useState<Record<string, boolean>>({});
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const viewport = wrapRef.current?.querySelector('[data-slot="scroll-area-viewport"]');
    if (viewport) viewport.scrollTo({ top: viewport.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const runQuery = useCallback(async (q: string) => {
    if (!q.trim() || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", query: q }]);
    setBusy(true);
    try {
      const result = await api.copilotQuery(q.trim());
      setMessages((m) => [...m, { role: "copilot", query: q, result }]);
    } catch (e) {
      const err = e as { status?: number };
      const msg = err.status === 401
        ? "Unauthorized. Sign in to the backend first."
        : err.status === 409
          ? "No data loaded yet. Ingest the datasets first."
          : (e as { message?: string })?.message ?? "Co-pilot call failed.";
      setMessages((m) => [...m, { role: "copilot", query: q, error: msg }]);
    } finally {
      setBusy(false);
    }
  }, [busy]);

  const toggle = (key: string) => setExpanded((e) => ({ ...e, [key]: !e[key] }));
  const toggleTree = (key: string) => setTreeOpen((t) => ({ ...t, [key]: !t[key] }));
  const toggleExplain = (key: string) => setExplainOpen((x) => ({ ...x, [key]: !x[key] }));
  const setMsgTab = (i: number, t: "evidence" | "timeline" | "graph" | "sql") =>
    setTab((x) => ({ ...x, [String(i)]: t }));

  const exportRecords = (records: CopilotRecord[]) => {
    const csv = csvFromRecords(records);
    if (!csv) return;
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `copilot_evidence_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const sortedRecords = (records: CopilotRecord[], msgIdx: number) => {
    const dir = sortDir[String(msgIdx)] ?? "desc";
    const key = records[0] && ("transaction_amount" in records[0] ? "transaction_amount" : "timestamp" in records[0] ? "timestamp" : "");
    if (!key) return records;
    const val = (r: CopilotRecord) => Number(r[key]) || 0;
    return [...records].sort((a, b) => (dir === "asc" ? val(a) - val(b) : val(b) - val(a)));
  };

  const timelineEvents = useMemo(() => {
    const out: { ts: string; kind: string; label: string }[] = [];
    for (let i = 0; i < messages.length; i++) {
      const m = messages[i];
      if (m.role !== "copilot" || !m.result) continue;
      for (const r of m.result.records) {
        const ts =
          r.timestamp || r.call_start_time || r.session_start_time || r.tx_time || r.created || "";
        if (!ts) continue;
        const kind =
          r.call_start_time ? "telecom"
          : r.session_start_time ? "internet"
          : "financial";
        const account = r.sender_account_number || r.account_no || r.receiver_account_number || "";
        out.push({
          ts: fmtDate(String(ts)),
          kind,
          label: `${r.transaction_id || r.cdr_id || r.ipdr_id || "record"} · ${fmtINR(Number(r.transaction_amount ?? r.amount) || null)}${account ? ` · ${account}` : ""}`,
        });
      }
    }
    return out.sort((a, b) => a.ts.localeCompare(b.ts));
  }, [messages]);

  const KIND_CLS: Record<string, string> = {
    financial: "border-l-blue-500/70",
    telecom: "border-l-emerald-500/70",
    internet: "border-l-violet-500/70",
  };
  const KIND_LABEL: Record<string, string> = {
    financial: "FIN",
    telecom: "CDR",
    internet: "IPDR",
  };

  const resultTabs = (i: number, r: CopilotQueryResult) => {
    const active = tab[String(i)] ?? (r.records.length ? "evidence" : "graph");
    const records = sortedRecords(r.records, i);
    const cols = r.records.length
      ? Object.keys(r.records[0]).filter((k) => !["risk_score", "risk_band"].includes(k)).slice(0, 9)
      : [];
    const riskCol = r.records.some((rec) => typeof rec.risk_score === "number");

    return (
      <div className="border border-border rounded-lg overflow-hidden">
        <div className="flex items-center gap-1 px-2 pt-2 bg-muted/40 border-b border-border">
          {(["evidence", "timeline", "graph", "sql"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setMsgTab(i, t)}
              className={cn(
                "px-3 py-1.5 text-xs font-semibold rounded-t-md transition-colors",
                active === t
                  ? "bg-background border border-border border-b-background text-emerald-500"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {t === "evidence" ? "Evidence" : t === "timeline" ? "Timeline" : t === "graph" ? "Graph" : "SQL (Dev)"}
            </button>
          ))}
          <div className="ml-auto pr-1 pb-1">
            <Button variant="ghost" size="sm" className="h-6 text-[11px]" onClick={() => exportRecords(r.records)}>
              <Download className="h-3 w-3 mr-1" /> CSV
            </Button>
          </div>
        </div>

        {active === "evidence" && (
          <div className="overflow-x-auto max-h-[360px] overflow-y-auto">
            {records.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">No records returned.</p>
            ) : (
              <table className="w-full text-xs">
                <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                  <tr>
                    {riskCol && <th className="px-2.5 py-2 text-left font-medium">Risk</th>}
                    {cols.map((k) => (
                      <th
                        key={k}
                        className="px-2.5 py-2 text-left font-medium whitespace-nowrap cursor-pointer hover:text-foreground"
                        onClick={() => {
                          const dir = sortDir[String(i)] === "asc" ? "desc" : "asc";
                          if (k === "transaction_amount" || k === "timestamp") {
                            setSortDir((s) => ({ ...s, [String(i)]: dir }));
                          }
                        }}
                      >
                        {k}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {records.map((rec, ri) => (
                    <tr
                      key={ri}
                      className={cn(
                        "border-t border-border/50 hover:bg-muted/30 transition-colors",
                        ROW_BAND_CLS[String(rec.risk_band ?? "LOW")]
                      )}
                    >
                      {riskCol && (
                        <td className="px-2.5 py-1.5 whitespace-nowrap">
                          <Badge variant="outline" className={cn("text-[10px]", RISK_BAND_CLS[String(rec.risk_band ?? "LOW")])}>
                            {rec.risk_score} · {rec.risk_band}
                          </Badge>
                        </td>
                      )}
                      {cols.map((k) => {
                        const v = rec[k];
                        const display = k === "transaction_amount" || k === "amount" || k === "total_amount"
                          ? fmtINR(Number(v))
                          : k.includes("time") || k === "timestamp"
                            ? fmtDate(String(v))
                            : String(v ?? "");
                        const clickable = isEntityKey(k) && v != null && String(v) !== "";
                        return (
                          <td key={k} className="px-2.5 py-1.5 font-mono whitespace-nowrap">
                            {clickable ? (
                              <button
                                onClick={() => runQuery(`Trace all activity for ${String(v)}`)}
                                title={`Investigate ${v}`}
                                className="text-emerald-500 hover:text-emerald-300 hover:underline"
                              >
                                {display}
                              </button>
                            ) : (
                              display
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {active === "timeline" && (
          <div className="p-3 max-h-[360px] overflow-y-auto space-y-1.5">
            {timelineEvents.length === 0 ? (
              <p className="text-sm text-muted-foreground">No timestamped events in this session yet.</p>
            ) : (
              timelineEvents.map((ev, ei) => (
                <div key={ei} className={cn("border-l-4 pl-3 py-1 text-xs", KIND_CLS[ev.kind])}>
                  <span className="font-mono text-muted-foreground">{ev.ts}</span>
                  <Badge variant="outline" className="ml-2 text-[9px]">{KIND_LABEL[ev.kind]}</Badge>
                  <span className="ml-2 text-foreground/90">{ev.label}</span>
                </div>
              ))
            )}
          </div>
        )}

        {active === "graph" && (
          <div className="p-3 max-h-[360px] overflow-y-auto space-y-3">
            {!r.linking_tree && (
              <p className="text-sm text-muted-foreground">
                No linking tree for this query — mention a phone, account or transaction ID to build one.
              </p>
            )}
            {r.linking_tree && !r.linking_tree.found && (
              <p className="text-sm text-muted-foreground">Entity not found in the observation network.</p>
            )}
            {r.linking_tree?.found && r.linking_tree.layers?.map((layer) => (
              <div key={layer.label}>
                <div className="text-[11px] font-bold uppercase tracking-wider text-cyan-500 mb-1.5">
                  {layer.label} ({layer.entities.length})
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {layer.entities.map((n) => {
                    const meta = ENTITY_TYPE_META[n.type] ?? ENTITY_TYPE_META.identifier;
                    const Icon = meta.icon;
                    const openKey = `n-${layer.layer}-${n.id}`;
                    const isOpen = treeNodeOpen[openKey];
                    return (
                      <div key={n.id} className="relative">
                        <button
                          onClick={() => {
                            setTreeNodeOpen((s) => ({ ...s, [openKey]: !s[openKey] }));
                            runQuery(`Trace all activity for ${n.id}`);
                          }}
                          className={cn(
                            "flex items-center gap-1.5 border rounded-full px-2.5 py-1 font-mono text-[10px] transition-colors hover:scale-[1.04]",
                            meta.cls
                          )}
                          title={`${meta.label} — click to investigate`}
                        >
                          <Icon className="h-3 w-3" />
                          {n.id}
                          {n.name && n.name !== "Unknown Entity" && <span className="text-muted-foreground">· {n.name}</span>}
                        </button>
                        {isOpen && (
                          <div className="absolute z-10 mt-1 left-0 w-56 bg-card border border-border rounded-lg p-2 text-[11px] space-y-1 shadow-xl">
                            <p className="font-mono text-muted-foreground break-all">{n.id}</p>
                            <p className="text-muted-foreground">type: {meta.label} · hop {n.hop_distance}</p>
                            <Button size="sm" className="h-6 w-full text-[10px]" onClick={() => runQuery(`Trace the 3-hop mule flow from ${n.id}`)}>
                              <Network className="h-3 w-3 mr-1" /> Continue Investigation
                            </Button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
                {layer.transactions.length > 0 && (
                  <div className="mt-1.5 space-y-1">
                    {layer.transactions.slice(0, 4).map((t) => (
                      <div key={t.txn_id} className="text-[11px] font-mono bg-muted/30 rounded px-2 py-1 flex items-center gap-2">
                        <CreditCard className="h-3 w-3 text-cyan-400 shrink-0" />
                        <span className="truncate">{t.txn_id} · {fmtINR(t.amount)} · {t.mode} · {t.sender} → {t.receiver}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {r.linking_tree?.found && r.linking_tree.layers && (
              <p className="text-[10px] text-muted-foreground">
                {r.linking_tree.total_nodes ?? "?"} nodes · {r.linking_tree.total_edges ?? "?"} edges · {r.linking_tree.max_hops} hops
              </p>
            )}
          </div>
        )}

        {active === "sql" && (
          <div className="space-y-2 p-3 max-h-[360px] overflow-y-auto">
            <div className="border border-border rounded-lg overflow-hidden">
              <button
                onClick={() => toggle(`cot-${i}`)}
                className="w-full flex items-center justify-between px-3 py-2 bg-muted/50 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground"
              >
                <span className="flex items-center gap-1.5"><Brain className="h-3.5 w-3.5" /> Chain of Thought</span>
                {expanded[`cot-${i}`] ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              {expanded[`cot-${i}`] && (
                <div className="p-3 space-y-2">
                  {r.chain_of_thought.map((step) => (
                    <div key={step.step} className="text-xs">
                      <span className="font-bold text-emerald-500">Step {step.step} · {step.title}</span>
                      <p className="text-muted-foreground mt-0.5">{step.content}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="border border-border rounded-lg overflow-hidden">
              <button
                onClick={() => toggle(`sql-${i}`)}
                className="w-full flex items-center justify-between px-3 py-2 bg-muted/50 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground"
              >
                <span className="flex items-center gap-1.5"><FileCode2 className="h-3.5 w-3.5" /> Generated SQL</span>
                {expanded[`sql-${i}`] ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              {expanded[`sql-${i}`] && (
                <pre className="p-3 text-[11px] font-mono text-cyan-400 overflow-x-auto bg-black/40">{r.generated_sql}</pre>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-12rem)]">
      <Card className="lg:col-span-2 flex flex-col overflow-hidden">
        <CardContent className="p-0 flex-1 flex flex-col overflow-hidden">
          <div ref={wrapRef} className="flex-1 overflow-hidden flex flex-col">
            <ScrollArea className="flex-1">
              <div className="p-4 space-y-4">
                {messages.length === 0 && (
                  <div className="flex flex-col items-center justify-center h-full min-h-[380px] text-center px-8">
                    <div className="w-16 h-16 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center mb-4">
                      <Brain className="h-8 w-8 text-emerald-500" />
                    </div>
                    <h2 className="text-xl font-bold text-foreground mb-2">OmniWatcher Investigative Co-Pilot</h2>
                    <p className="text-sm text-muted-foreground max-w-md mb-6">
                      Enter <span className="font-mono text-emerald-500">any identifier</span> — phone, account,
                      transaction ID, IMEI, IP or complaint number — to open an investigation. Every answer
                      returns an AI investigation summary, evidence metrics, pattern insights, a linking
                      tree and recommended next actions.
                    </p>
                    <div className="flex flex-wrap justify-center gap-2">
                      {SUGGESTIONS.map((s) => (
                        <Button key={s} variant="outline" size="sm" onClick={() => runQuery(s)} className="text-xs">
                          {s}
                        </Button>
                      ))}
                    </div>
                  </div>
                )}

                {messages.map((m, i) => (
                  <div key={i} className={cn("flex gap-3", m.role === "user" ? "justify-end" : "justify-start")}>
                    {m.role === "copilot" && (
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center shrink-0 mt-1">
                        <Bot className="h-4 w-4 text-emerald-500" />
                      </div>
                    )}
                    <div className={cn("max-w-[94%] space-y-2", m.role === "user" ? "order-first" : "")}>
                      {m.role === "user" && (
                        <div className="bg-emerald-600/90 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm">
                          {m.query}
                        </div>
                      )}

                      {m.role === "copilot" && m.error && (
                        <div className="bg-red-950/30 border border-red-500/30 text-red-400 rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm">
                          {m.error}
                        </div>
                      )}

                      {m.role === "copilot" && m.result && (
                        <div className="bg-muted/40 border border-border rounded-2xl rounded-tl-sm p-4 space-y-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline" className="text-emerald-500 border-emerald-500/40">
                              <Lightbulb className="h-3 w-3 mr-1" /> {m.result.intent}
                            </Badge>
                            <Badge variant="secondary" className="font-mono">
                              {m.result.investigation_summary.found_transactions} records
                            </Badge>
                            {m.result.graph_traversal?.found && (
                              <Badge className="bg-cyan-500/10 text-cyan-400 border-cyan-500/40">
                                <Network className="h-3 w-3 mr-1" /> 3-hop graph · {m.result.graph_traversal.total_nodes} nodes
                              </Badge>
                            )}
                          </div>

                          {m.result.entity_resolution.resolved && (
                            <div className="flex items-center gap-2 text-xs bg-emerald-950/20 border border-emerald-500/25 rounded-lg px-3 py-2">
                              <Compass className="h-3.5 w-3.5 text-emerald-500" />
                              <span className="text-muted-foreground">Resolved</span>
                              <span className="font-mono text-foreground">{m.result.entity_resolution.entity_id}</span>
                              <ArrowRight className="h-3 w-3 text-muted-foreground" />
                              <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 uppercase">
                                {(ENTITY_TYPE_META[m.result.entity_resolution.entity_type] ?? ENTITY_TYPE_META.identifier).label}
                              </Badge>
                            </div>
                          )}

                          {/* INVESTIGATION SUMMARY */}
                          <div className="border border-border rounded-lg overflow-hidden">
                            <div className="bg-muted/50 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-foreground flex items-center gap-1.5">
                              <ShieldAlert className="h-3.5 w-3.5 text-emerald-500" /> Investigation Summary
                            </div>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-border/60">
                              {[
                                ["Transactions", m.result.investigation_summary.found_transactions.toLocaleString()],
                                ["Total Amount", fmtINR(m.result.investigation_summary.total_amount)],
                                ["Highest Risk", m.result.investigation_summary.highest_risk ? `${m.result.investigation_summary.highest_risk}/100` : "—"],
                                ["Primary Account", m.result.investigation_summary.primary_account || "—"],
                                ["Common Phone", m.result.investigation_summary.common_phone || "—"],
                                ["Linked IPs", m.result.investigation_summary.linked_ips || 0],
                                ["Beneficiaries", m.result.investigation_summary.linked_beneficiaries || 0],
                                ["Top Receiver", m.result.investigation_summary.top_receiver || "—"],
                              ].map(([label, val]) => (
                                <div key={label as string} className="bg-card px-3 py-2">
                                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
                                  <p className="font-mono text-sm text-foreground truncate" title={String(val)}>{String(val)}</p>
                                </div>
                              ))}
                            </div>
                            <div className="px-3 py-2 bg-muted/20 border-t border-border">
                              <p className="text-[11px] text-foreground/80 leading-relaxed">
                                <Sparkles className="h-3 w-3 inline mr-1 text-emerald-500" />
                                {m.result.investigation_summary.narrative}
                              </p>
                            </div>
                          </div>

                          {/* QUICK METRICS */}
                          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground font-mono">
                            <span>{m.result.metrics.records} records</span>
                            <span>{fmtINR(m.result.metrics.total_amount)}</span>
                            <span>{m.result.metrics.accounts} accounts</span>
                            <span>{m.result.metrics.phones} phones</span>
                            <span>{m.result.metrics.ips} IPs</span>
                            <span>{m.result.metrics.beneficiaries} beneficiaries</span>
                            <span>peak {m.result.metrics.highest_risk}</span>
                            <span>avg {m.result.metrics.avg_risk}</span>
                          </div>

                          {/* AI INSIGHTS */}
                          {m.result.insights.length > 0 && (
                            <div>
                              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1.5">
                                <Lightbulb className="h-3.5 w-3.5 text-yellow-500" /> AI Generated Insights
                              </div>
                              <div className="space-y-1.5">
                                {m.result.insights.map((ins, ii) => (
                                  <div key={ii} className={cn("border rounded-lg px-3 py-2", INSIGHT_CLS[ins.severity] ?? "border-border")}>
                                    <p className="text-xs font-semibold">{ins.title}</p>
                                    <p className="text-[11px] text-muted-foreground mt-0.5">{ins.detail}</p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* NEXT ACTIONS */}
                          {m.result.suggestions.length > 0 && (
                            <div>
                              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1.5">
                                <Compass className="h-3.5 w-3.5 text-cyan-500" /> Recommended Next Actions
                              </div>
                              <div className="flex flex-wrap gap-1.5">
                                {m.result.suggestions.map((s, si) => (
                                  <Button
                                    key={si}
                                    variant="outline"
                                    size="sm"
                                    className="text-[11px]"
                                    onClick={() => runQuery(s.query)}
                                    title={s.why}
                                  >
                                    {s.action} · <span className="font-mono text-emerald-500">{s.target}</span>
                                  </Button>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* EXPLAIN THIS RESULT */}
                          <div className="border border-border rounded-lg overflow-hidden">
                            <button
                              onClick={() => toggleExplain(`ex-${i}`)}
                              className="w-full flex items-center justify-between px-3 py-2 bg-muted/50 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground"
                            >
                              <span className="flex items-center gap-1.5"><Brain className="h-3.5 w-3.5" /> Explain This Result</span>
                              {explainOpen[`ex-${i}`] ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                            </button>
                            {explainOpen[`ex-${i}`] && (
                              <ul className="p-3 space-y-1.5">
                                {m.result.explanation.map((line, ei) => (
                                  <li key={ei} className="text-[11px] text-muted-foreground flex gap-2">
                                    <span className="text-emerald-500 shrink-0">•</span>
                                    <span>{line}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>

                          {resultTabs(i, m.result)}
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {busy && (
                  <div className="flex gap-3">
                    <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center shrink-0 mt-1">
                      <Bot className="h-4 w-4 text-emerald-500" />
                    </div>
                    <div className="bg-muted/40 border border-border rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-muted-foreground animate-pulse">
                      <Database className="h-4 w-4 inline mr-2" />
                      Running evidentiary pipeline...
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>

          <div className="p-3 border-t border-border">
            <form
              className="flex gap-2"
              onSubmit={(e) => { e.preventDefault(); runQuery(input); }}
            >
              <Input
                ref={inputRef}
                className="flex-1"
                placeholder="Enter any identifier or ask a question…  (Ctrl+K to focus)"
                value={input}
                onChange={(e) => setInput(e.target.value)}
              />
              <Button type="submit" disabled={busy || !input.trim()}>
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </CardContent>
      </Card>

      <Card className="hidden lg:flex flex-col overflow-hidden">
        <CardContent className="p-4 space-y-4 overflow-y-auto">
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2 flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-emerald-500" /> Investigation Path
            </div>
            <div className="space-y-1">
              {messages.filter((mm) => mm.role === "user").length === 0 && (
                <p className="text-xs text-muted-foreground">Your session path will appear here.</p>
              )}
              {messages
                .map((mm, mi) => ({ mm, mi }))
                .filter(({ mm }) => mm.role === "user")
                .map(({ mm, mi }) => (
                  <button
                    key={mi}
                    onClick={() => runQuery(mm.query ?? "")}
                    className="w-full text-left text-[11px] font-mono text-cyan-400 bg-muted/30 hover:bg-muted/60 rounded-lg px-3 py-2 transition-colors truncate"
                    title="Re-run this step"
                  >
                    {mm.query}
                  </button>
                ))}
            </div>
          </div>

          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2 flex items-center gap-1.5">
              <Brain className="h-3.5 w-3.5 text-emerald-500" /> What can it do?
            </div>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" />
                Universal entry: phone, account, transaction ID, IMEI, IP, complaint — auto-resolved
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" />
                AI investigation summary + evidence metrics first, SQL hidden in Dev tab
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" />
                Pattern insights: repeated beneficiaries, night activity, velocity bursts
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" />
                3-hop linking tree with clickable nodes — continue investigations recursively
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" />
                Next-action suggestions with one-click execution
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" />
                Risk-colored evidence table, timeline tab, CSV export, explainability
              </li>
            </ul>
          </div>

          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
              Sample questions
            </div>
            <div className="space-y-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => runQuery(s)}
                  className="w-full text-left text-xs font-mono text-cyan-400 bg-muted/30 hover:bg-muted/60 rounded-lg px-3 py-2 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
