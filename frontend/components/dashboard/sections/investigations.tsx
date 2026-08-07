"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  FolderOpen, Plus, Trash2, Gavel, AlertTriangle, FileText,
  StickyNote, ShieldAlert, Loader2, GitBranch, ArrowLeft,
} from "lucide-react";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { api, type Investigation, type InvestigationTree } from "@/lib/api";

const KIND_ICONS: Record<string, React.ElementType> = {
  alert: ShieldAlert,
  transaction: FileText,
  note: StickyNote,
};

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-red-500/10 text-red-500 border-red-500/20",
  high: "bg-orange-500/10 text-orange-500 border-orange-500/20",
  medium: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
  low: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
};

const BAND_STYLES: Record<string, string> = {
  CRITICAL: "bg-red-500/10 text-red-500 border-red-500/20",
  HIGH: "bg-orange-500/10 text-orange-500 border-orange-500/20",
  MEDIUM: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
  LOW: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  SAFE: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
};

const fmtDate = (iso: string) =>
  iso ? new Date(iso).toLocaleString([], { hour: "2-digit", minute: "2-digit" }) : "";

export function InvestigationsSection() {
  const [cases, setCases] = useState<Investigation[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newNotes, setNewNotes] = useState("");
  const [creatingSaving, setCreatingSaving] = useState(false);

  const [selected, setSelected] = useState<Investigation | null>(null);
  const [tree, setTree] = useState<InvestigationTree | null>(null);
  const [treeLoading, setTreeLoading] = useState(false);

  const [fkKind, setFkKind] = useState("alert");
  const [fkSeverity, setFkSeverity] = useState("medium");
  const [fkTitle, setFkTitle] = useState("");
  const [fkDetail, setFkDetail] = useState("");
  const [fkSaving, setFkSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api
      .investigations()
      .then((res) => {
        setCases(res.investigations || []);
        if (selected) {
          const fresh = (res.investigations || []).find((i) => i.id === selected.id);
          if (fresh) setSelected(fresh);
        }
      })
      .catch((error) => {
        const err = error as { status?: number };
        toast.error(err.status === 401 ? "Session expired. Please log in again." : "Failed to load investigations.");
      })
      .finally(() => setLoading(false));
  }, [selected?.id]);

  useEffect(() => {
    load();
  }, [load]);

  const createCase = async () => {
    if (!newTitle.trim()) {
      toast.error("A case title is required.");
      return;
    }
    setCreatingSaving(true);
    try {
      const res = await api.createInvestigation(newTitle.trim(), newNotes.trim());
      setCases((prev) => [res.investigation, ...prev]);
      setSelected(res.investigation);
      setNewTitle("");
      setNewNotes("");
      setCreating(false);
      toast.success("Investigation opened.");
    } catch (e) {
      toast.error((e as { message?: string })?.message ?? "Failed to create investigation.");
    } finally {
      setCreatingSaving(false);
    }
  };

  const addFinding = async () => {
    if (!selected) return;
    if (!fkTitle.trim()) {
      toast.error("A finding title is required.");
      return;
    }
    setFkSaving(true);
    try {
      const res = await api.addFinding(selected.id, {
        kind: fkKind,
        title: fkTitle.trim(),
        detail: fkDetail.trim(),
        severity: fkSeverity,
      });
      setSelected((prev) =>
        prev ? { ...prev, findings: [...prev.findings, res.finding] } : prev
      );
      setTree(null);
      setFkTitle("");
      setFkDetail("");
      toast.success("Finding attached to the case.");
    } catch (e) {
      toast.error((e as { message?: string })?.message ?? "Failed to add finding.");
    } finally {
      setFkSaving(false);
    }
  };

  const openTree = async (id: number) => {
    setTreeLoading(true);
    try {
      setTree(await api.investigationTree(id));
    } catch (e) {
      toast.error((e as { message?: string })?.message ?? "Failed to load the case tree.");
    } finally {
      setTreeLoading(false);
    }
  };

  const deleteCase = async (inv: Investigation) => {
    try {
      await api.deleteInvestigation(inv.id);
      setCases((prev) => prev.filter((i) => i.id !== inv.id));
      if (selected?.id === inv.id) {
        setSelected(null);
        setTree(null);
      }
      toast.success("Investigation deleted.");
    } catch (e) {
      const err = e as { status?: number; message?: string };
      toast.error(err.status === 403 ? "Admin role required to delete cases." : err.message ?? "Failed to delete investigation.");
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium">Open Cases</CardTitle>
          <Button size="sm" onClick={() => setCreating((v) => !v)}>
            <Plus className="w-4 h-4 mr-1" /> New Case
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          <AnimatePresence>
            {creating && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="border border-border rounded-lg p-4 space-y-3 bg-muted/20">
                  <Input
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="Case title, e.g. FIR 123/2025 — UPI mule network"
                  />
                  <Textarea
                    value={newNotes}
                    onChange={(e) => setNewNotes(e.target.value)}
                    placeholder="Initial notes (optional)"
                    rows={2}
                  />
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => setCreating(false)}>
                      Cancel
                    </Button>
                    <Button size="sm" onClick={createCase} disabled={creatingSaving}>
                      {creatingSaving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Gavel className="w-4 h-4 mr-1" />}
                      Open Case
                    </Button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {loading && <p className="text-sm text-muted-foreground py-4 text-center">Loading cases…</p>}
          {!loading && cases.length === 0 && (
            <p className="text-sm text-muted-foreground py-6 text-center">
              No investigations yet. Open a case to track flagged transactions and findings.
            </p>
          )}
          {!loading &&
            cases.map((inv) => (
              <div
                key={inv.id}
                className={`flex items-center justify-between gap-3 border rounded-lg p-3 transition-colors cursor-pointer ${
                  selected?.id === inv.id
                    ? "border-emerald-500/40 bg-emerald-500/5"
                    : "border-border hover:bg-muted/40"
                }`}
                onClick={() => {
                  setSelected(inv);
                  setTree(null);
                }}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <FolderOpen className="w-4 h-4 text-emerald-500 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{inv.title}</p>
                    <p className="text-xs text-muted-foreground">
                      #{inv.id} · {inv.findings.length} findings · updated {fmtDate(inv.updated)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Badge variant="outline" className={inv.status === "open" ? "text-emerald-500 border-emerald-500/30" : ""}>
                    {inv.status}
                  </Badge>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteCase(inv);
                    }}
                    title="Delete case (admin)"
                    className="p-1.5 rounded-md text-muted-foreground hover:text-red-400 hover:bg-secondary transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
        </CardContent>
      </Card>

      <AnimatePresence mode="wait">
        {selected && (
          <motion.div
            key={selected.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="grid gap-6 lg:grid-cols-2"
          >
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Gavel className="w-4 h-4 text-emerald-500" />
                  Case #{selected.id} — {selected.title}
                </CardTitle>
                {selected.notes && (
                  <CardDescription className="text-xs whitespace-pre-wrap">{selected.notes}</CardDescription>
                )}
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => openTree(selected.id)} disabled={treeLoading}>
                      {treeLoading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <GitBranch className="w-4 h-4 mr-1" />}
                      Case Tree
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setTree(null)}>
                      <ArrowLeft className="w-4 h-4 mr-1" /> Findings
                    </Button>
                  </div>
                </div>

                {tree ? (
                  <ScrollArea className="max-h-[420px]">
                    <div className="space-y-3">
                      <p className="text-xs text-muted-foreground font-mono uppercase tracking-wider">
                        {tree.flagged_transactions.length} flagged transaction(s) linked from findings
                      </p>
                      {tree.flagged_transactions.length === 0 && (
                        <p className="text-sm text-muted-foreground">
                          No flagged transactions yet. Add a finding whose title/detail mentions a transaction ID.
                        </p>
                      )}
                      {tree.flagged_transactions.map((leg) => (
                        <div key={leg.transaction_id} className="border border-border rounded-lg p-3 space-y-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono text-xs text-foreground">{leg.transaction_id}</span>
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className={BAND_STYLES[leg.risk_band] ?? ""}>
                                {leg.risk_band} · {leg.risk_score}
                              </Badge>
                            </div>
                          </div>
                          {leg.receiver_account && (
                            <p className="text-xs text-muted-foreground">→ receiver {leg.receiver_account}</p>
                          )}
                          <div className="flex flex-wrap gap-1">
                            {leg.rules_fired.slice(0, 5).map((r) => (
                              <Badge key={r} variant="outline" className="text-[10px]">{r}</Badge>
                            ))}
                          </div>
                          {leg.evidence.length > 0 && (
                            <p className="text-[11px] text-muted-foreground border-t border-border pt-2">
                              {leg.evidence.slice(0, 3).join(" · ")}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                ) : (
                  <>
                    <div className="space-y-3">
                      {selected.findings.length === 0 && (
                        <p className="text-sm text-muted-foreground py-4 text-center">
                          No findings yet. Attach evidence, alerts, or transactions below.
                        </p>
                      )}
                      {selected.findings.map((f) => {
                        const Icon = KIND_ICONS[f.kind] ?? StickyNote;
                        return (
                          <div key={f.id} className="border border-border rounded-lg p-3">
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2 min-w-0">
                                <Icon className="w-4 h-4 text-emerald-500 shrink-0" />
                                <span className="text-sm font-medium text-foreground truncate">{f.title}</span>
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                <Badge variant="outline" className="text-[10px]">{f.kind}</Badge>
                                <Badge variant="outline" className={SEVERITY_STYLES[f.severity] ?? ""}>
                                  {f.severity}
                                </Badge>
                              </div>
                            </div>
                            {f.detail && <p className="text-xs text-muted-foreground mt-1.5">{f.detail}</p>}
                            <p className="text-[11px] text-muted-foreground/70 mt-1.5">{fmtDate(f.created)}</p>
                          </div>
                        );
                      })}
                    </div>

                    <div className="border-t border-border mt-4 pt-4 space-y-2">
                      <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Attach finding</p>
                      <div className="flex gap-2">
                        <Select value={fkKind} onValueChange={setFkKind}>
                          <SelectTrigger className="w-[140px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="alert">Alert</SelectItem>
                            <SelectItem value="transaction">Transaction</SelectItem>
                            <SelectItem value="note">Note</SelectItem>
                          </SelectContent>
                        </Select>
                        <Select value={fkSeverity} onValueChange={setFkSeverity}>
                          <SelectTrigger className="w-[140px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="low">Low</SelectItem>
                            <SelectItem value="medium">Medium</SelectItem>
                            <SelectItem value="high">High</SelectItem>
                            <SelectItem value="critical">Critical</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <Input
                        value={fkTitle}
                        onChange={(e) => setFkTitle(e.target.value)}
                        placeholder="Title — mention a transaction ID to flag it in the case tree"
                      />
                      <Textarea
                        value={fkDetail}
                        onChange={(e) => setFkDetail(e.target.value)}
                        placeholder="Detail / evidence summary (optional)"
                        rows={2}
                      />
                      <div className="flex justify-end">
                        <Button size="sm" onClick={addFinding} disabled={fkSaving}>
                          {fkSaving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <AlertTriangle className="w-4 h-4 mr-1" />}
                          Attach Finding
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-emerald-500" />
                  Linked Evidence
                </CardTitle>
                <CardDescription className="text-xs">
                  Flagged transactions detected across this case's findings.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {tree?.flagged_transactions.map((leg) => (
                    <div key={leg.transaction_id} className="border border-border rounded-lg p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs">{leg.transaction_id}</span>
                        <Badge variant="outline" className={BAND_STYLES[leg.risk_band] ?? ""}>{leg.risk_band}</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        risk {leg.risk_score} · {leg.rules_fired.length} rules
                      </p>
                    </div>
                  ))}
                  {(!tree || tree.flagged_transactions.length === 0) && (
                    <p className="text-sm text-muted-foreground py-8 text-center">
                      Click <span className="font-mono">Case Tree</span> to scan findings for flagged transaction IDs.
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
