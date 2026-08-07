"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Landmark,
  Phone,
  Smartphone,
  Globe,
  AtSign,
  User,
  FileDown,
  Loader2,
  AlertTriangle,
  ArrowUpDown,
  Clock,
  PhoneCall,
  Network,
} from "lucide-react";
import { api, type EntityIntelligence, type RelationshipIntel } from "@/lib/api";
import { toast } from "sonner";

type PanelData =
  | { type: "entity"; info: EntityIntelligence }
  | { type: "relationship"; rel: RelationshipIntel };

const BAND_CLASS: Record<string, string> = {
  CRITICAL: "bg-red-500/15 text-red-400 border-red-500/30",
  HIGH: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  MEDIUM: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  LOW: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
};

const KIND_ICON: Record<string, React.ElementType> = {
  account: Landmark,
  phone: Phone,
  device: Smartphone,
  ip: Globe,
  upi: AtSign,
  name: User,
  imei: Smartphone,
  imsi: Smartphone,
};

const fmtMoney = (n: number) => "Rs " + Math.round(n).toLocaleString("en-IN");

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h4>
      {children}
    </div>
  );
}

function Kpi({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-lg border border-border bg-secondary/30 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={`font-mono text-sm font-semibold ${accent ?? "text-foreground"}`}>{value}</p>
    </div>
  );
}

export function InvestigationPanel({
  data,
  onClose,
  onEntitySelect,
}: {
  data: PanelData | null;
  onClose: () => void;
  onEntitySelect: (kind: string, value: string) => void;
}) {
  const [downloading, setDownloading] = useState(false);
  if (!data) return null;

  const download = async () => {
    if (data.type !== "entity") return;
    setDownloading(true);
    try {
      await api.downloadEntityReport(data.info.kind, data.info.value);
      toast.success("STR downloaded");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Report download failed");
    } finally {
      setDownloading(false);
    }
  };

  const entity = data.type === "entity" ? data.info : null;
  const rel = data.type === "relationship" ? data.rel : null;
  const Icon = entity ? KIND_ICON[entity.kind] ?? Network : ArrowUpDown;
  const title = entity
    ? `${entity.kind.toUpperCase()} — ${entity.value}`
    : rel
      ? `${rel.a} ↔ ${rel.b}`
      : "";

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[88vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="rounded-lg border border-border bg-secondary/40 p-2">
              <Icon className="h-5 w-5 text-emerald-500" />
            </div>
            <div className="min-w-0">
              <DialogTitle className="font-mono text-base break-all">{title}</DialogTitle>
              {entity && (
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <Badge className={BAND_CLASS[entity.risk_band] ?? BAND_CLASS.LOW}>
                    {entity.risk_band} risk
                  </Badge>
                  <span className="font-mono text-lg font-bold text-foreground">
                    {entity.risk_score}
                    <span className="text-muted-foreground">/100</span>
                  </span>
                  <span className="text-xs text-muted-foreground">
                    confidence {Math.round(entity.confidence * 100)}%
                  </span>
                </div>
              )}
            </div>
          </div>
        </DialogHeader>

        {entity && (
          <div className="space-y-5">
            <div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-yellow-500 to-red-500"
                  style={{ width: `${entity.risk_score}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Composite risk score — never a black box: every rule below contributes points.
              </p>
            </div>

            <Section title="Why this risk score?">
              {entity.breakdown.length > 0 ? (
                <div className="divide-y divide-border overflow-hidden rounded-lg border border-border">
                  {entity.breakdown.map((b, i) => (
                    <div key={i} className="flex items-start gap-3 bg-secondary/20 px-3 py-2">
                      <span className="mt-0.5 shrink-0 rounded bg-red-500/15 px-1.5 py-0.5 font-mono text-xs font-bold text-red-400">
                        +{b.points}
                      </span>
                      <div className="min-w-0">
                        <p className="font-mono text-xs font-semibold text-foreground">{b.rule}</p>
                        <p className="text-xs text-muted-foreground">{b.reason}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No rules fired — score is low. No unexplained risk.
                </p>
              )}
              {entity.flags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {entity.flags.map((f) => (
                    <Badge key={f} variant="outline" className="font-mono text-[10px]">
                      {f}
                    </Badge>
                  ))}
                </div>
              )}
            </Section>

            <Section title="Activity footprint">
              <div className="grid grid-cols-2 gap-2">
                <Kpi label="Transactions" value={String(entity.counts.transactions)} />
                <Kpi label="Calls" value={String(entity.counts.calls)} />
                <Kpi label="SMS" value={String(entity.counts.sms)} />
                <Kpi label="IP sessions" value={String(entity.counts.ip_sessions)} />
                <Kpi label="Total credits" value={fmtMoney(entity.volumes.credit)} accent="text-emerald-500" />
                <Kpi label="Total debits" value={fmtMoney(entity.volumes.debit)} accent="text-red-400" />
                <Kpi label="Avg amount" value={fmtMoney(entity.volumes.avg_amount)} />
                <Kpi label="Largest" value={fmtMoney(entity.volumes.max_amount)} />
                <Kpi label="Round payouts" value={String(entity.volumes.round_amounts)} />
              </div>
              <div className="flex items-center gap-2 rounded-lg border border-border bg-secondary/20 px-3 py-2 text-xs text-muted-foreground">
                <Clock className="h-3.5 w-3.5" />
                <span className="font-mono">{entity.activity.first ?? "—"}</span>
                <span>→</span>
                <span className="font-mono">{entity.activity.last ?? "—"}</span>
              </div>
            </Section>

            {entity.patterns.length > 0 && (
              <Section title="Suspicious patterns detected">
                <div className="space-y-2">
                  {entity.patterns.map((p, i) => (
                    <div key={i} className="flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" />
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-foreground">{p.label}</p>
                        <p className="text-xs text-muted-foreground">{p.evidence}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {Object.entries(entity.links).some(([, v]) => v.length > 0) && (
              <Section title="Linked entities">
                <div className="space-y-2">
                  {Object.entries(entity.links).map(([cat, items]) =>
                    items.length > 0 ? (
                      <div key={cat} className="flex flex-wrap items-center gap-1.5">
                        <span className="w-32 shrink-0 text-xs text-muted-foreground">{cat}</span>
                        {items.slice(0, 10).map((v) => (
                          <button
                            key={v}
                            onClick={() => {
                              const kind =
                                cat === "phones" || cat === "contacts"
                                  ? "phone"
                                  : cat === "accounts" || cat === "receiver_accounts"
                                    ? "account"
                                    : cat === "imeis"
                                      ? "imei"
                                      : cat === "ips"
                                        ? "ip"
                                        : cat === "upi_ids"
                                          ? "upi"
                                          : cat === "counterparties"
                                            ? "name"
                                            : "name";
                              onEntitySelect(kind, v);
                            }}
                            className="rounded-md border border-border bg-secondary/40 px-2 py-0.5 font-mono text-[11px] text-foreground transition-colors hover:border-emerald-500/40 hover:text-emerald-500"
                            title="Open entity card"
                          >
                            {v}
                          </button>
                        ))}
                      </div>
                    ) : null
                  )}
                </div>
              </Section>
            )}

            {entity.ncrp.length > 0 && (
              <Section title="NCRP complaints">
                <p className="text-sm text-muted-foreground">
                  {entity.ncrp.length} complaint ledger row(s) reference this entity.
                </p>
              </Section>
            )}

            {entity.records.length > 0 && (
              <Section title="Recent evidence records">
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-secondary/60 text-left uppercase tracking-wider text-muted-foreground">
                        <th className="px-2.5 py-1.5 font-medium">Type</th>
                        <th className="px-2.5 py-1.5 font-medium">When</th>
                        <th className="px-2.5 py-1.5 font-medium">Detail</th>
                        <th className="px-2.5 py-1.5 text-right font-medium">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {entity.records.map((r, i) => (
                        <tr key={i} className="hover:bg-secondary/30">
                          <td className="px-2.5 py-1.5 font-mono uppercase text-emerald-500">{r.kind}</td>
                          <td className="px-2.5 py-1.5 whitespace-nowrap text-muted-foreground">
                            {r.date} {r.time}
                          </td>
                          <td className="max-w-[280px] truncate px-2.5 py-1.5">{r.label}</td>
                          <td className="px-2.5 py-1.5 text-right font-mono">
                            {r.amount != null ? fmtMoney(r.amount) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>
            )}
          </div>
        )}

        {rel && (
          <div className="space-y-5">
            {rel.calls && (
              <Section title="Communication evidence">
                <div className="grid grid-cols-2 gap-2">
                  <Kpi label="Calls" value={String(rel.calls.count)} />
                  <Kpi label="Total duration" value={`${rel.calls.total_seconds}s`} />
                  <Kpi label="Avg duration" value={`${rel.calls.avg_seconds}s`} />
                  <Kpi label="Longest" value={`${rel.calls.max_seconds}s`} />
                </div>
                <div className="flex items-center gap-2 rounded-lg border border-border bg-secondary/20 px-3 py-2 text-xs text-muted-foreground">
                  <PhoneCall className="h-3.5 w-3.5" />
                  <span className="font-mono">{rel.calls.first ?? "—"}</span>
                  <span>→</span>
                  <span className="font-mono">{rel.calls.last ?? "—"}</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(rel.calls.by_type).map(([t, n]) => (
                    <Badge key={t} variant="outline" className="font-mono text-[10px]">
                      {t} × {n}
                    </Badge>
                  ))}
                </div>
              </Section>
            )}

            {rel.money && (
              <Section title="Money-flow evidence">
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-secondary/60 text-left uppercase tracking-wider text-muted-foreground">
                        <th className="px-2.5 py-1.5 font-medium">Leg</th>
                        <th className="px-2.5 py-1.5 text-right font-medium">Count</th>
                        <th className="px-2.5 py-1.5 text-right font-medium">Total</th>
                        <th className="px-2.5 py-1.5 text-right font-medium">Avg</th>
                        <th className="px-2.5 py-1.5 text-right font-medium">Round</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {rel.money.legs.map((l, i) => (
                        <tr key={i} className="hover:bg-secondary/30">
                          <td className="px-2.5 py-1.5 font-mono">{l.direction}</td>
                          <td className="px-2.5 py-1.5 text-right font-mono">{l.count}</td>
                          <td className="px-2.5 py-1.5 text-right font-mono">{fmtMoney(l.total)}</td>
                          <td className="px-2.5 py-1.5 text-right font-mono">{fmtMoney(l.avg)}</td>
                          <td className="px-2.5 py-1.5 text-right font-mono">{l.round_amounts}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>
            )}

            {rel.indicators.length > 0 && (
              <Section title="Laundering / behavioural indicators">
                <div className="space-y-2">
                  {rel.indicators.map((ind, i) => (
                    <div key={i} className="flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" />
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-foreground">{ind.label}</p>
                        <p className="text-xs text-muted-foreground">{ind.evidence}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {rel.coincidences.length > 0 && (
              <Section title="Bank ↔ telecom coincidences">
                <div className="space-y-2">
                  {rel.coincidences.map((c, i) => (
                    <div key={i} className="rounded-lg border border-border bg-secondary/20 px-3 py-2 text-xs">
                      <p className="text-muted-foreground">
                        {c.txn_ts} · {c.mode} · <span className="font-mono text-foreground">{fmtMoney(c.amount)}</span>
                        <span className="text-muted-foreground"> — calls in ±{c.window_min}min window:</span>
                      </p>
                      <p className="mt-1 font-mono text-emerald-500">
                        {c.calls_in_window.map((w) => `[${w.ts}] ${w.type}→${w.b}`).join("  ")}
                      </p>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {rel.evidence.length > 0 && (
              <Section title="Supporting evidence">
                <div className="space-y-1.5">
                  {rel.evidence.map((e, i) => (
                    <p key={i} className="rounded-md bg-secondary/20 px-2.5 py-1.5 font-mono text-[11px] text-muted-foreground">
                      {e}
                    </p>
                  ))}
                </div>
              </Section>
            )}

            {!rel.calls && !rel.money && rel.evidence.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No direct relationship found between these two entities in the loaded data.
              </p>
            )}
          </div>
        )}

        <div className="mt-2 flex items-center justify-between gap-2 border-t border-border pt-4">
          {entity ? (
            <Button onClick={download} disabled={downloading} variant="outline" className="gap-2">
              {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileDown className="h-4 w-4" />}
              Download STR
            </Button>
          ) : (
            <span />
          )}
          <Button onClick={onClose} variant="ghost">
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
