"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Clock, Banknote, PhoneCall, Globe, ShieldAlert, type LucideIcon } from "lucide-react";
import { api, type TimelineEvent } from "@/lib/api";
import { toast } from "sonner";

const KIND_STYLE: Record<string, { label: string; cls: string; icon: LucideIcon }> = {
  bank: { label: "BANK", cls: "bg-emerald-500/10 text-emerald-500 border-emerald-500/30", icon: Banknote },
  cdr: { label: "CDR", cls: "bg-blue-500/10 text-blue-500 border-blue-500/30", icon: PhoneCall },
  ipdr: { label: "IPDR", cls: "bg-purple-500/10 text-purple-500 border-purple-500/30", icon: Globe },
  complaint: { label: "NCRP", cls: "bg-red-500/10 text-red-500 border-red-500/30", icon: ShieldAlert },
};

export function TimelineSection() {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [filter, setFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .timeline(5000)
      .then((res) => setEvents(res.events))
      .catch((e) => toast.error(e.status === 409 ? "No data loaded." : "Failed to load timeline."))
      .finally(() => setLoading(false));
  }, []);

  const shown = filter ? events.filter((e) => e.kind === filter) : events;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center gap-2 flex-wrap">
          <Clock className="h-5 w-5 text-emerald-500" />
          <CardTitle>Unified Event Timeline</CardTitle>
          <CardDescription>
            {loading ? "…" : `${events.length.toLocaleString()} fused events`}
          </CardDescription>
          <div className="ml-auto flex gap-2">
            {[null, "bank", "cdr", "ipdr", "complaint"].map((k) => (
              <button
                key={k || "all"}
                onClick={() => setFilter(k)}
                className={`px-3 py-1 rounded-full text-xs border transition-colors ${
                  filter === k
                    ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-500"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {k === null ? "ALL" : k.toUpperCase()}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[calc(100vh-20rem)]">
            {loading ? (
              <div className="p-8 text-center text-muted-foreground animate-pulse">Loading timeline...</div>
            ) : shown.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                No events. Run the ingestion pipeline first.
              </div>
            ) : (
              <div className="relative">
                <div className="absolute left-[19px] top-0 bottom-0 w-px bg-border" />
                {shown.map((e, i) => {
                  const style = KIND_STYLE[e.kind] || KIND_STYLE.bank;
                  const Icon = style.icon;
                  return (
                    <div key={i} className="relative flex gap-4 px-5 py-3">
                      <div className={`w-10 h-10 rounded-lg border flex items-center justify-center z-10 ${style.cls}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs text-foreground">{e.date}</span>
                          <Badge variant="outline" className={style.cls}>
                            {style.label}
                          </Badge>
                          <span className="font-mono text-xs text-muted-foreground">{e.entity}</span>
                        </div>
                        <p className="text-sm text-muted-foreground mt-1 break-words">
                          {e.detail || e.label || "—"}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
