"""Graph Engine package: co-occurrence, construction, centrality, communities, metrics.

This package implements the Graph Engine (Fase 6) as an independent sibling
to statistics/, feature_engineering/, and probability/. It reads draws only
through its own DrawReader Protocol (A9) and writes only to graph_* tables.

Methods (GM-01..GM-05):
- GM-01: Co-occurrence (joint pair counts)
- GM-02: Graph Construction (adjacency from co-occurrence)
- GM-03: Centrality (degree, closeness, betweenness)
- GM-04: Communities (pure-greedy modularity)
- GM-05: Network Metrics (density, modularity score)

Dependencies: stdlib only (D8). No networkx/numpy/scipy.
"""

from backend.app.graph.cooccurrence import DrawReader

__all__ = ["DrawReader"]
