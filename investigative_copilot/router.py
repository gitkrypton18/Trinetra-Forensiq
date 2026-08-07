"""FastAPI router for OmniWatcher Investigative Co-Pilot."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

from backend import auth

from .copilot_engine import InvestigativeCoPilotEngine
from .db_builder import get_copilot_db, reset_copilot_db
from .prompts import SAMPLE_QUERIES_PROMPT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/copilot", tags=["Investigative Co-Pilot"])

# Lazy engine initialization, rebuilt whenever the loaded bundle changes.
_engine: Optional[InvestigativeCoPilotEngine] = None
_engine_bundle: Optional[Dict[str, Any]] = None


def _current_bundle() -> Optional[Dict[str, Any]]:
    from backend import api
    return api._state.get("bundle")


def reset_engine() -> None:
    """Drops the cached engine + copilot DB; next request rebuilds from the
    currently loaded bundle. Called by the API on ingest / clear / restore."""
    global _engine, _engine_bundle
    _engine = None
    _engine_bundle = None
    reset_copilot_db()


def get_engine() -> InvestigativeCoPilotEngine:
    global _engine, _engine_bundle
    bundle = _current_bundle()
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no data loaded; POST /ingest first"
        )
    if _engine is None or _engine_bundle is not bundle:
        _engine = InvestigativeCoPilotEngine(conn=get_copilot_db(bundle),
                                             bundle=bundle)
        _engine_bundle = bundle
    return _engine


class QueryRequest(BaseModel):
    query: str = Field(..., json_schema_extra={"example": "Show me all accounts that received money within 5 minutes of a call originating from West Bengal tower locations."})


class ClusterSummaryRequest(BaseModel):
    entity_ids: List[str] = Field(..., json_schema_extra={"example": ["ACC_1001", "ACC_1002"]})


@router.post("/query")
def process_investigative_query(payload: QueryRequest,
                                user: dict = Depends(auth.require_user)) -> Dict[str, Any]:
    """Processes a natural language investigative query and returns Evidentiary Chain-of-Thought, SQL, and graph trace."""
    try:
        engine = get_engine()
        result = engine.analyze_query(payload.query)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing copilot query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )


@router.post("/summarize-cluster")
def summarize_entity_cluster(payload: ClusterSummaryRequest,
                             user: dict = Depends(auth.require_user)) -> Dict[str, Any]:
    """Generates an executive lead summary paragraph for a cluster of clicked nodes/transactions."""
    try:
        engine = get_engine()
        result = engine.summarize_cluster(payload.entity_ids)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating cluster summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )


@router.get("/schema")
def get_database_schema(user: dict = Depends(auth.require_user)) -> Dict[str, Any]:
    """Returns database schema definition and sample questions for UI prompt assistance."""
    return {
        "tables": [
            "bank_transactions",
            "cdr_records",
            "ipdr_records",
            "bank_cdr_links",
            "cdr_ipdr_links",
            "anomaly_records",
            "complaints",
            "subscribers"
        ],
        "sample_queries": [
            "Show me all accounts that received money within 5 minutes of a call originating from West Bengal tower locations.",
            "Trace the 3-hop money flow from mule account ACC_1001.",
            "Find all UPI transactions greater than ₹50,000 where the sender was in active CDR call.",
            "List top receiver accounts that rapidly layered funds via IMPS."
        ],
        "prompt_help": SAMPLE_QUERIES_PROMPT
    }


@router.get("/stats")
def get_copilot_stats(user: dict = Depends(auth.require_user)) -> Dict[str, Any]:
    """Returns database statistics for the Co-Pilot module."""
    try:
        engine = get_engine()
        conn = engine.conn
        cursor = conn.cursor()
        
        counts = {}
        tables = ["bank_transactions", "cdr_records", "ipdr_records",
                  "bank_cdr_links", "cdr_ipdr_links", "anomaly_records",
                  "complaints", "subscribers"]
        for t in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as c FROM {t}")
                counts[t] = cursor.fetchone()["c"]
            except Exception:
                counts[t] = 0

        return {
            "dataset_source": engine.dataset_source,
            "tables": counts,
            "graph_nodes": engine.graph_engine.graph.number_of_nodes(),
            "graph_edges": engine.graph_engine.graph.number_of_edges(),
            "max_graph_hops": 3
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/{entity_id}")
def get_entity_graph(entity_id: str, max_hops: int = 3,
                     user: dict = Depends(auth.require_user)) -> Dict[str, Any]:
    """Returns the 3-hop NetworkX graph structure (nodes, edges, layers) for an entity or transaction."""
    try:
        engine = get_engine()
        result = engine.graph_engine.trace_mule_chain(entity_id, max_hops=max_hops)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching entity graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tree/{entity_id}")
def get_entity_linking_tree(entity_id: str, max_hops: int = 3,
                            user: dict = Depends(auth.require_user)) -> Dict[str, Any]:
    """Returns the complete linking tree for an entity/transaction: accounts,
    phones and their transactions/calls grouped by hop layer."""
    try:
        engine = get_engine()
        result = engine.graph_engine.linking_tree(entity_id, max_hops=max_hops)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching linking tree: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph-html/{entity_id}")
def get_entity_graph_html(entity_id: str, max_hops: int = 3,
                          user: dict = Depends(auth.require_user)):
    """Returns an interactive standalone HTML Network Diagram for viewing in browser."""
    from fastapi.responses import HTMLResponse
    try:
        engine = get_engine()
        res = engine.graph_engine.trace_mule_chain(entity_id, max_hops=max_hops)
        
        nodes = res.get("nodes", [])[:100]
        edges = res.get("edges", [])[:200]
        
        vis_nodes = []
        for n in nodes:
            nid = str(n["node_id"])
            ntype = n.get("type", "account")
            color = "#1E88E5" if ntype == "account" else ("#8E24AA" if ntype == "phone" else "#FB8C00")
            label = f"{n.get('name', nid)}\n({nid})" if n.get("name") and n.get("name") != "Unknown Entity" else nid
            vis_nodes.append({"id": nid, "label": label, "color": color, "shape": "dot", "size": 18 - (n.get("hop_distance", 0) * 3)})

        vis_edges = []
        for e in edges:
            etype = e.get("edge_type", "link")
            label = f"₹{e['amount']:,.0f}" if "amount" in e else (f"{e['duration']}s" if "duration" in e else etype)
            color = "#43A047" if etype == "bank_transfer" else "#3949AB"
            vis_edges.append({"from": str(e["source"]), "to": str(e["target"]), "label": label, "color": color, "arrows": "to"})

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>OmniWatcher 3-Hop Network Graph: {entity_id}</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{ font-family: sans-serif; margin: 0; background: #0F172A; color: #F8FAFC; }}
        #header {{ padding: 15px 20px; background: #1E293B; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }}
        #network {{ width: 100vw; height: calc(100vh - 70px); }}
        .badge {{ background: #3B82F6; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-left: 5px; }}
    </style>
</head>
<body>
    <div id="header">
        <h2>OmniWatcher Forensic Graph — Entity: <span style="color:#60A5FA">{entity_id}</span></h2>
        <div>
            <span class="badge">Max Hops: {max_hops}</span>
            <span class="badge" style="background:#10B981">Nodes: {len(nodes)}</span>
            <span class="badge" style="background:#8B5CF6">Edges: {len(edges)}</span>
        </div>
    </div>
    <div id="network"></div>
    <script type="text/javascript">
        var container = document.getElementById('network');
        var data = {{
            nodes: new vis.DataSet({vis_nodes}),
            edges: new vis.DataSet({vis_edges})
        }};
        var options = {{
            nodes: {{ font: {{ color: '#F8FAFC', size: 12 }} }},
            edges: {{ font: {{ color: '#94A3B8', size: 10, align: 'middle' }} }},
            physics: {{ barnesHut: {{ gravitationalConstant: -3000, springLength: 120 }} }}
        }};
        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>"""
        return HTMLResponse(content=html_content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rendering graph HTML: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
