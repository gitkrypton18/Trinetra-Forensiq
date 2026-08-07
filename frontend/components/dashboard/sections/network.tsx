"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Network,
  Phone,
  Landmark,
  GitFork,
  RotateCw,
  Crosshair,
  Smartphone,
  Globe,
  Filter,
} from "lucide-react";
import { api, type EgoNet, type Phone as PhoneProfile, type MoneyGraph, type EntityIntelligence, type RelationshipIntel } from "@/lib/api";
import { toast } from "sonner";
import { InvestigationPanel } from "@/components/dashboard/investigation-panel";

type Tab = "calls" | "money" | "link" | "device" | "ip" | "coincidence";
type PanelPayload =
  | { type: "entity"; info: EntityIntelligence }
  | { type: "relationship"; rel: RelationshipIntel };

const riskColor = (risk?: number) => {
  if ((risk ?? 0) >= 75) return "#ef4444";
  if ((risk ?? 0) >= 50) return "#f97316";
  return "#34d399";
};

function GraphNode({
  x,
  y,
  r,
  id,
  kind,
  risk,
  onClick,
}: {
  x: number;
  y: number;
  r: number;
  id: string;
  kind?: string;
  risk?: number;
  onClick: () => void;
}) {
  const fill =
    kind === "device" ? "oklch(0.55 0.18 240)"
    : kind === "ip" ? "oklch(0.6 0.15 280)"
    : kind === "account" ? "oklch(0.6 0.15 255)"
    : kind === "phone" ? "oklch(0.25 0.02 260)"
    : "oklch(0.28 0.03 260)";
  const stroke = kind === "phone" && risk !== undefined ? riskColor(risk) : "oklch(0.7 0.18 145)";
  return (
    <g onClick={onClick} className="cursor-pointer" role="button" aria-label={`Inspect ${id}`}>
      <circle cx={x} cy={y} r={r + 6} fill="transparent" />
      <circle cx={x} cy={y} r={r} fill={fill} stroke={stroke} strokeWidth={2} />
      <text x={x} y={y + 3} textAnchor="middle" fontSize="9" fill="oklch(0.95 0 0)" className="font-mono pointer-events-none">
        {id.length > 11 ? `${id.slice(0, 11)}…` : id}
      </text>
      <title>{`${id} · ${kind ?? "node"}${risk !== undefined ? ` · risk ${risk}/100` : ""} — click to inspect`}</title>
    </g>
  );
}

function GraphEdge({
  x1,
  y1,
  x2,
  y2,
  color,
  opacity,
  width,
  onClick,
  hint,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
  opacity: number;
  width: number;
  onClick: () => void;
  hint?: string;
}) {
  return (
    <g>
      <line
        x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={color}
        strokeOpacity={opacity}
        strokeWidth={width}
      />
      <line
        x1={x1} y1={y1} x2={x2} y2={y2}
        stroke="transparent"
        strokeWidth={Math.max(10, width + 6)}
        onClick={onClick}
        className="cursor-pointer"
        style={{ pointerEvents: "stroke" }}
      >
        <title>{hint ?? "Click to inspect this relationship"}</title>
      </line>
    </g>
  );
}

function CallGraphView({
  graph,
  onNodeClick,
  onEdgeClick,
}: {
  graph: EgoNet;
  onNodeClick: (id: string) => void;
  onEdgeClick: (a: string, b: string) => void;
}) {
  const nodes = graph.nodes;
  const center = graph.node;
  const positions: Record<string, { x: number; y: number }> = { [center]: { x: 0, y: 0 } };
  const n = nodes.length;
  nodes.forEach((node, i) => {
    const angle = (i / Math.max(n, 1)) * 2 * Math.PI;
    const r = 170;
    positions[node.id] = { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
  });

  const size = 560;
  return (
    <svg viewBox={`${-size / 2} ${-size / 2} ${size} ${size}`} className="w-full max-h-[560px]">
      {graph.edges.map((e, i) => {
        const p1 = positions[e.source];
        const p2 = positions[e.target];
        if (!p1 || !p2) return null;
        const ev = e.evidence?.[0];
        return (
          <GraphEdge
            key={i}
            x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
            color="oklch(0.7 0.18 145)"
            opacity={Math.min(1, e.weight / 20)}
            width={Math.min(6, Math.max(0.5, e.weight / 5))}
            onClick={() => onEdgeClick(e.source, e.target)}
            hint={ev ?? `${e.weight} calls — click for relationship evidence`}
          />
        );
      })}
      <circle r={8} fill="oklch(0.7 0.18 145)" />
      <GraphNode x={0} y={0} r={11} id={center} kind="phone" risk={graph.nodes.find((x) => x.id === center)?.risk} onClick={() => onNodeClick(center)} />
      {nodes.map((node) => {
        const p = positions[node.id];
        if (!p) return null;
        const r = Math.min(26, 10 + (node.degree ?? 0));
        return (
          <GraphNode
            key={node.id}
            x={p.x} y={p.y} r={r}
            id={node.id}
            kind="phone"
            risk={node.risk}
            onClick={() => onNodeClick(node.id)}
          />
        );
      })}
    </svg>
  );
}

function LayerGraphView({
  graph,
  onNodeClick,
  onEdgeClick,
  size = 560,
}: {
  graph: EgoNet;
  onNodeClick: (id: string, kind?: string) => void;
  onEdgeClick: (a: string, b: string) => void;
  size?: number;
}) {
  const nodes = graph.nodes;
  const center = graph.node;
  const positions: Record<string, { x: number; y: number }> = { [center]: { x: 0, y: 0 } };
  nodes.forEach((node, i) => {
    const angle = (i / Math.max(nodes.length, 1)) * 2 * Math.PI;
    positions[node.id] = { x: Math.cos(angle) * 160, y: Math.sin(angle) * 160 };
  });
  return (
    <svg viewBox={`${-size / 2} ${-size / 2} ${size} ${size}`} className="w-full max-h-[560px]">
      {graph.edges.map((e, i) => {
        const p1 = positions[e.source];
        const p2 = positions[e.target];
        if (!p1 || !p2) return null;
        const shared = e.kind === "shared";
        return (
          <GraphEdge
            key={i}
            x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
            color={shared ? "oklch(0.6 0.15 240)" : "oklch(0.6 0.2 145)"}
            opacity={0.55}
            width={Math.min(5, 1 + e.weight / 3)}
            onClick={() => onEdgeClick(e.source, e.target)}
            hint={e.evidence?.[0] ?? "relationship"}
          />
        );
      })}
      <GraphNode x={0} y={0} r={12} id={center} kind="phone" onClick={() => onNodeClick(center, "phone")} />
      {nodes.map((node) => {
        const p = positions[node.id];
        if (!p) return null;
        return (
          <GraphNode
            key={node.id}
            x={p.x} y={p.y} r={9}
            id={node.id}
            kind={node.kind}
            risk={node.risk}
            onClick={() => onNodeClick(node.id, node.kind)}
          />
        );
      })}
    </svg>
  );
}

function MoneyGraphView({
  graph,
  onNodeClick,
  onEdgeClick,
}: {
  graph: MoneyGraph;
  onNodeClick: (id: string, kind?: string) => void;
  onEdgeClick: (a: string, b: string) => void;
}) {
  const positions: Record<string, { x: number; y: number }> = {};
  const nodes = graph.nodes.slice(0, 120);
  nodes.forEach((node, i) => {
    const angle = (i / Math.max(nodes.length, 1)) * 2 * Math.PI;
    positions[node.id] = { x: Math.cos(angle) * 220, y: Math.sin(angle) * 220 };
  });

  const size = 620;
  const maxAmount = Math.max(1, ...graph.edges.map((e) => e.amount));
  return (
    <svg viewBox={`${-size / 2} ${-size / 2} ${size} ${size}`} className="w-full max-h-[620px]">
      {graph.edges.map((e, i) => {
        const p1 = positions[e.source];
        const p2 = positions[e.target];
        if (!p1 || !p2) return null;
        const opacity = 0.25 + 0.75 * (e.amount / maxAmount);
        return (
          <GraphEdge
            key={i}
            x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
            color="oklch(0.62 0.2 25)"
            opacity={opacity}
            width={Math.max(0.6, (e.amount / maxAmount) * 6)}
            onClick={() => onEdgeClick(e.source, e.target)}
            hint={`Rs ${Math.round(e.amount).toLocaleString("en-IN")} moved — click for money-flow evidence`}
          />
        );
      })}
      {nodes.map((node) => {
        const p = positions[node.id];
        if (!p) return null;
        const isAccount = node.kind === "account";
        return (
          <GraphNode
            key={node.id}
            x={p.x} y={p.y}
            r={isAccount ? 9 : 6}
            id={node.id}
            kind={node.kind}
            onClick={() => onNodeClick(node.id, node.kind)}
          />
        );
      })}
    </svg>
  );
}

function LinkGraphView({
  graph,
  onNodeClick,
  onEdgeClick,
}: {
  graph: MoneyGraph;
  onNodeClick: (id: string, kind?: string) => void;
  onEdgeClick: (a: string, b: string) => void;
}) {
  const accounts = graph.nodes.filter((node) => node.kind === "account").slice(0, 80);
  const phones = graph.nodes.filter((node) => node.kind !== "account").slice(0, 80);
  const positions: Record<string, { x: number; y: number }> = {};
  accounts.forEach((node, i) => {
    positions[node.id] = { x: -230, y: -220 + (i / Math.max(accounts.length, 1)) * 440 };
  });
  phones.forEach((node, i) => {
    positions[node.id] = { x: 230, y: -220 + (i / Math.max(phones.length, 1)) * 440 };
  });

  const size = 620;
  return (
    <svg viewBox={`${-size / 2} ${-size / 2} ${size} ${size}`} className="w-full max-h-[620px]">
      {graph.edges.slice(0, 600).map((e, i) => {
        const p1 = positions[e.source];
        const p2 = positions[e.target];
        if (!p1 || !p2) return null;
        return (
          <GraphEdge
            key={i}
            x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
            color="oklch(0.6 0.15 255)"
            opacity={0.45}
            width={0.8}
            onClick={() => onEdgeClick(e.source, e.target)}
            hint="account ↔ phone link — click for evidence"
          />
        );
      })}
      {Object.entries(positions).map(([id, p]) => {
        const node = graph.nodes.find((x) => x.id === id);
        const isAccount = node?.kind === "account";
        return (
          <GraphNode
            key={id}
            x={p.x} y={p.y}
            r={isAccount ? 8 : 5}
            id={id}
            kind={isAccount ? "account" : "phone"}
            onClick={() => onNodeClick(id, isAccount ? "account" : "phone")}
          />
        );
      })}
    </svg>
  );
}

const fmtMoney = (n: number) => "Rs " + Math.round(n).toLocaleString("en-IN");

export function NetworkSection() {
  const [tab, setTab] = useState<Tab>("calls");
  const [phones, setPhones] = useState<PhoneProfile[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [mode, setMode] = useState<"evidence" | "full">("evidence");
  const [graph, setGraph] = useState<EgoNet | null>(null);
  const [moneyGraph, setMoneyGraph] = useState<MoneyGraph | null>(null);
  const [linkGraph, setLinkGraph] = useState<MoneyGraph | null>(null);
  const [deviceGraph, setDeviceGraph] = useState<EgoNet | null>(null);
  const [ipGraph, setIpGraph] = useState<EgoNet | null>(null);
  const [hits, setHits] = useState<{ phone: string; account_no: string; txn_date: string; mode: string; amount: number; phone_cdr_records: number; window_count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [panel, setPanel] = useState<PanelPayload | null>(null);
  const [panelBusy, setPanelBusy] = useState(false);

  const openEntity = useCallback((kind: string, value: string) => {
    if (!value) return;
    setPanelBusy(true);
    setPanel(null);
    api
      .entity(kind, value)
      .then((info) => setPanel({ type: "entity", info }))
      .catch((e) =>
        toast.error(e.status === 409 ? "No data loaded." : `No evidence card for ${kind} ${value}.`)
      )
      .finally(() => setPanelBusy(false));
  }, []);

  const openRelationship = useCallback((a: string, b: string) => {
    if (!a || !b) return;
    setPanelBusy(true);
    setPanel(null);
    api
      .relationship(a, b)
      .then((rel) => setPanel({ type: "relationship", rel }))
      .catch((e) => toast.error(e.status === 409 ? "No data loaded." : "Failed to load relationship."))
      .finally(() => setPanelBusy(false));
  }, []);

  const loadTab = useCallback(
    (t: Tab, phone?: string) => {
      setLoading(true);
      const loaders: Record<Tab, Promise<unknown>> = {
        calls: phone
          ? api.egonet(phone, 1, mode).then((g) => setGraph(g))
          : Promise.resolve(),
        money: api.moneyGraph(1000, 300).then((g) => setMoneyGraph(g)),
        link: api.accountPhoneGraph(200).then((g) => setLinkGraph(g)),
        device: phone ? api.deviceGraph(phone).then((g) => setDeviceGraph(g)) : Promise.resolve(),
        ip: phone ? api.ipGraph(phone).then((g) => setIpGraph(g)) : Promise.resolve(),
        coincidence: api.coincidence(3600, 100).then((r) => setHits(r.hits)),
      };
      loaders[t]
        .catch((e) =>
          toast.error(
            e.status === 409
              ? "No data loaded."
              : t === "calls" || t === "device" || t === "ip"
                ? "Failed to load network graph."
                : "Failed to load graph."
          )
        )
        .finally(() => setLoading(false));
    },
    [mode]
  );

  useEffect(() => {
    api
      .phones(0, 100)
      .then((res) => {
        setPhones(res.phones);
        if (res.phones.length > 0) {
          const top = res.phones[0].phone;
          setSelected(top);
          loadTab("calls", top);
        } else {
          loadTab("calls");
        }
      })
      .catch((e) => toast.error(e.status === 409 ? "No data loaded." : "Failed to load phones."));
  }, [loadTab]);

  const switchTab = (t: Tab) => {
    setTab(t);
    loadTab(t, selected ?? undefined);
  };

  const loadEgo = (phone: string) => {
    setSelected(phone);
    setTab("calls");
    loadTab("calls", phone);
  };

  const nodeKindOf = (id: string, kind?: string): string => {
    if (kind === "account") return "account";
    if (kind === "device") return "imei";
    if (kind === "ip") return "ip";
    if (kind === "phone") return "phone";
    if (id.includes("@")) return "upi";
    if (/^\d{10,}$/.test(id.replace(/\D/g, ""))) return "phone";
    return "name";
  };

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: "calls", label: "Call Network", icon: Phone },
    { id: "money", label: "Money Flow", icon: Landmark },
    { id: "link", label: "Accounts ↔ Phones", icon: GitFork },
    { id: "device", label: "Device / IMEI", icon: Smartphone },
    { id: "ip", label: "IP Layer", icon: Globe },
    { id: "coincidence", label: "Correlations", icon: Crosshair },
  ];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center gap-2 flex-wrap">
          <Network className="h-5 w-5 text-emerald-500" />
          <CardTitle>Investigation Network</CardTitle>
          <CardDescription>
            Evidence-first graphs — click any node or edge to open its intelligence card
          </CardDescription>
          <div className="ml-auto flex items-center gap-1 flex-wrap">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => switchTab(t.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  tab === t.id
                    ? "bg-emerald-500/15 text-emerald-500 border border-emerald-500/30"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary border border-transparent"
                }`}
              >
                <t.icon className="w-4 h-4" />
                <span className="hidden sm:inline">{t.label}</span>
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {tab === "calls" && (
            <div className="flex flex-col items-center gap-4">
              <div className="flex items-center gap-2 w-full max-w-2xl flex-wrap justify-center">
                <Select value={selected ?? undefined} onValueChange={loadEgo} disabled={loading || phones.length === 0}>
                  <SelectTrigger className="w-64">
                    <SelectValue placeholder="Select a phone" />
                  </SelectTrigger>
                  <SelectContent>
                    {phones.map((p) => (
                      <SelectItem key={p.phone} value={p.phone}>
                        {p.phone} · {p.records} calls
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="flex items-center rounded-lg border border-border p-0.5 text-xs">
                  <button
                    onClick={() => setMode("evidence")}
                    className={`flex items-center gap-1 rounded-md px-2.5 py-1.5 font-medium transition-colors ${
                      mode === "evidence" ? "bg-emerald-500/15 text-emerald-500" : "text-muted-foreground hover:text-foreground"
                    }`}
                    title="Only calls relevant to the investigation (high-risk contacts, suspicious money windows)"
                  >
                    <Filter className="h-3.5 w-3.5" />
                    Evidence
                  </button>
                  <button
                    onClick={() => setMode("full")}
                    className={`flex items-center gap-1 rounded-md px-2.5 py-1.5 font-medium transition-colors ${
                      mode === "full" ? "bg-emerald-500/15 text-emerald-500" : "text-muted-foreground hover:text-foreground"
                    }`}
                    title="Show the full call history"
                  >
                    Full
                  </button>
                </div>
                <button
                  onClick={() => selected && loadEgo(selected)}
                  className="p-2 rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors"
                  title="Refresh"
                >
                  <RotateCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                </button>
              </div>
              <div className="flex flex-col items-center justify-center min-h-[420px] w-full">
                {loading && <p className="text-muted-foreground animate-pulse">Loading graph...</p>}
                {!loading && !graph && (
                  <p className="text-muted-foreground">No network data. Run the ingestion pipeline first.</p>
                )}
                {!loading && graph && (
                  <CallGraphView
                    graph={graph}
                    onNodeClick={(id) => openEntity("phone", id)}
                    onEdgeClick={openRelationship}
                  />
                )}
                {!loading && graph && (
                  <div className="mt-2 space-y-1 text-center">
                    <p className="text-xs text-muted-foreground">
                      {graph.node} ↔ {graph.nodes.length} contacts · {graph.edges.length} call links
                    </p>
                    {graph.filtered && !graph.fallback && (
                      <p className="text-[11px] text-muted-foreground">
                        Evidence mode: {graph.kept} of {graph.total} call links kept — calls near
                        suspicious money movement or involving high-risk entities
                      </p>
                    )}
                    {graph.fallback && (
                      <p className="text-[11px] text-amber-500/80">
                        No directly suspicious links for this phone — showing its top contacts by
                        call volume. Switch to Full mode for the complete history.
                      </p>
                    )}
                    <div className="flex items-center justify-center gap-3 text-[10px] text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full" style={{ background: "#34d399" }} /> low risk
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full" style={{ background: "#f97316" }} /> medium
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full" style={{ background: "#ef4444" }} /> high
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {tab === "money" && (
            <div className="flex flex-col items-center justify-center min-h-[420px]">
              {loading && <p className="text-muted-foreground animate-pulse">Computing money flows...</p>}
              {!loading && !moneyGraph && <p className="text-muted-foreground">No money-flow graph available.</p>}
              {!loading && moneyGraph && moneyGraph.edges.length === 0 && (
                <p className="text-muted-foreground">No significant flows (≥ Rs 1,000) found.</p>
              )}
              {!loading && moneyGraph && moneyGraph.edges.length > 0 && (
                <>
                  <MoneyGraphView
                    graph={moneyGraph}
                    onNodeClick={(id, kind) => openEntity(nodeKindOf(id, kind), id)}
                    onEdgeClick={openRelationship}
                  />
                  <p className="text-xs text-muted-foreground mt-2 font-mono">
                    {moneyGraph.stats.nodes} nodes · {moneyGraph.stats.edges} edges · edges ≥ Rs 1,000 ·
                    click nodes/edges for evidence
                  </p>
                </>
              )}
            </div>
          )}

          {tab === "link" && (
            <div className="flex flex-col items-center justify-center min-h-[420px]">
              {loading && <p className="text-muted-foreground animate-pulse">Linking accounts and phones...</p>}
              {!loading && !linkGraph && <p className="text-muted-foreground">No account–phone links found.</p>}
              {!loading && linkGraph && (
                <>
                  <LinkGraphView
                    graph={linkGraph}
                    onNodeClick={(id, kind) => openEntity(nodeKindOf(id, kind), id)}
                    onEdgeClick={openRelationship}
                  />
                  <p className="text-xs text-muted-foreground mt-2 font-mono">
                    {linkGraph.stats?.nodes ?? linkGraph.nodes.length} nodes ·{" "}
                    {linkGraph.stats?.edges ?? linkGraph.edges.length} links (narration + IPDR)
                  </p>
                </>
              )}
            </div>
          )}

          {tab === "device" && (
            <div className="flex flex-col items-center justify-center min-h-[420px]">
              {!phones.length && !loading && (
                <p className="text-muted-foreground">No phones in the loaded data.</p>
              )}
              {!selected && phones.length > 0 && (
                <p className="text-muted-foreground">Select a phone on the Call Network tab first.</p>
              )}
              {selected && (
                <>
                  {loading && <p className="text-muted-foreground animate-pulse">Building IMEI layer...</p>}
                  {!loading && deviceGraph && deviceGraph.edges.length === 0 && (
                    <p className="text-muted-foreground">
                      No IMEI/session data for {selected} in this dataset.
                    </p>
                  )}
                  {!loading && deviceGraph && deviceGraph.edges.length > 0 && (
                    <>
                      <LayerGraphView
                        graph={deviceGraph}
                        onNodeClick={(id, kind) => openEntity(nodeKindOf(id, kind), id)}
                        onEdgeClick={openRelationship}
                      />
                      <p className="text-xs text-muted-foreground mt-2 font-mono">
                        Devices used by {selected} and co-users (shared IMEI evidence)
                      </p>
                    </>
                  )}
                </>
              )}
            </div>
          )}

          {tab === "ip" && (
            <div className="flex flex-col items-center justify-center min-h-[420px]">
              {!phones.length && !loading && (
                <p className="text-muted-foreground">No phones in the loaded data.</p>
              )}
              {!selected && phones.length > 0 && (
                <p className="text-muted-foreground">Select a phone on the Call Network tab first.</p>
              )}
              {selected && (
                <>
                  {loading && <p className="text-muted-foreground animate-pulse">Building IP layer...</p>}
                  {!loading && ipGraph && ipGraph.edges.length === 0 && (
                    <p className="text-muted-foreground">
                      No IPDR sessions for {selected} in this dataset.
                    </p>
                  )}
                  {!loading && ipGraph && ipGraph.edges.length > 0 && (
                    <>
                      <LayerGraphView
                        graph={ipGraph}
                        onNodeClick={(id, kind) => openEntity(nodeKindOf(id, kind), id)}
                        onEdgeClick={openRelationship}
                      />
                      <p className="text-xs text-muted-foreground mt-2 font-mono">
                        IPs used by {selected} and co-users behind the same addresses
                      </p>
                    </>
                  )}
                </>
              )}
            </div>
          )}

          {tab === "coincidence" && (
            <div className="min-h-[420px]">
              {loading && <p className="text-muted-foreground animate-pulse py-8 text-center">Correlating timeline...</p>}
              {!loading && hits.length === 0 && (
                <p className="text-muted-foreground py-10 text-center">
                  No bank↔telecom coincidence windows found (≤ 60 min).
                </p>
              )}
              {!loading && hits.length > 0 && (
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-secondary/60 text-left text-xs uppercase tracking-wider text-muted-foreground">
                        <th className="px-4 py-2.5 font-medium">Phone</th>
                        <th className="px-4 py-2.5 font-medium">Account</th>
                        <th className="px-4 py-2.5 font-medium">Date</th>
                        <th className="px-4 py-2.5 font-medium">Mode</th>
                        <th className="px-4 py-2.5 font-medium text-right">Amount</th>
                        <th className="px-4 py-2.5 font-medium text-right">CDR records</th>
                        <th className="px-4 py-2.5 font-medium text-right">In window</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {hits.map((h, i) => (
                        <tr key={i} className="hover:bg-secondary/40 transition-colors cursor-pointer" onClick={() => openEntity("phone", h.phone)}>
                          <td className="px-4 py-2.5 font-mono text-emerald-500">{h.phone}</td>
                          <td className="px-4 py-2.5 font-mono">{h.account_no}</td>
                          <td className="px-4 py-2.5">{h.txn_date}</td>
                          <td className="px-4 py-2.5">{h.mode}</td>
                          <td className="px-4 py-2.5 text-right font-mono">{fmtMoney(h.amount)}</td>
                          <td className="px-4 py-2.5 text-right font-mono">{h.phone_cdr_records}</td>
                          <td className="px-4 py-2.5 text-right font-mono">{h.window_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
      <InvestigationPanel
        data={panel}
        onClose={() => setPanel(null)}
        onEntitySelect={openEntity}
      />
      {panelBusy && (
        <p className="fixed bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-border bg-background px-4 py-2 text-xs text-muted-foreground animate-pulse">
          Loading intelligence card...
        </p>
      )}
    </div>
  );
}
