"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Search, Loader2, Hash, Phone, Landmark, CreditCard, FileWarning, Globe } from "lucide-react";
import { api, type SearchResult } from "@/lib/api";
import { toast } from "sonner";

const KIND_META: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  account: { label: "Account", icon: Landmark, color: "text-emerald-500" },
  phone: { label: "Phone", icon: Phone, color: "text-cyan-500" },
  upi: { label: "UPI ID", icon: Hash, color: "text-amber-500" },
  imei: { label: "IMEI", icon: Hash, color: "text-violet-500" },
  imsi: { label: "IMSI", icon: Hash, color: "text-fuchsia-500" },
  ip: { label: "IP", icon: Globe, color: "text-sky-500" },
  complaint: { label: "NCRP Complaint", icon: FileWarning, color: "text-red-500" },
  transaction: { label: "Transaction", icon: CreditCard, color: "text-yellow-500" },
};

export function SearchSection() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    try {
      setResult(await api.search(query.trim()));
    } catch (e) {
      const err = e as { status?: number };
      toast.error(
        err.status === 409
          ? "No data loaded yet. Ingest datasets from the Data Ingestion section first."
          : "Search failed. Is the backend running?"
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Search className="h-5 w-5 text-emerald-500" />
            <CardTitle>Cross-Dataset Entity Search</CardTitle>
            <CardDescription>
              Accounts, phones, UPI IDs, IMEI, IMSI, IPs, transactions and NCRP complaints
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={run} className="flex gap-3">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. phone number, account no, UPI ID, IP address, name..."
              className="flex-1 h-11 px-4 rounded-lg bg-secondary border border-border text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/20 focus:border-accent"
            />
            <button
              type="submit"
              disabled={busy || !query.trim()}
              className="h-11 px-5 rounded-lg bg-emerald-500/90 hover:bg-emerald-500 text-black font-semibold text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {busy && <Loader2 className="w-4 h-4 animate-spin" />}
              Search
            </button>
          </form>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {result.total} result{result.total === 1 ? "" : "s"} for &quot;{result.query}&quot;
            </CardTitle>
          </CardHeader>
          <CardContent>
            {result.total === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">
                No matching entities found in the loaded datasets.
              </p>
            ) : (
              <div className="divide-y divide-border rounded-lg border border-border overflow-hidden">
                {result.results.map((r, i) => {
                  const meta = KIND_META[r.kind] ?? { label: r.kind, icon: Hash, color: "text-muted-foreground" };
                  const Icon = meta.icon;
                  return (
                    <div key={i} className="flex items-start gap-4 px-4 py-3 hover:bg-secondary/40 transition-colors">
                      <div className={`mt-0.5 ${meta.color}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline gap-2">
                          <span className="text-xs uppercase tracking-wider font-mono text-muted-foreground shrink-0">
                            {meta.label}
                          </span>
                          <span className="text-sm font-medium text-foreground truncate">{r.label}</span>
                        </div>
                        {(r.account_no || r.amount != null || r.date) && (
                          <p className="text-xs text-muted-foreground mt-0.5 font-mono">
                            {r.account_no && <span className="mr-3">acct {r.account_no}</span>}
                            {r.amount != null && <span className="mr-3">Rs {r.amount}</span>}
                            {r.date && <span>{r.date}</span>}
                          </p>
                        )}
                      </div>
                      {typeof r.txns === "number" && (
                        <span className="text-xs font-mono text-muted-foreground shrink-0">
                          {r.txns} txns
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
