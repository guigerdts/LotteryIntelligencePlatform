"""Backtesting engine: walk-forward validation (Fase 10, BTE-01..18).

Provides generic strategy evaluation against historical lottery data using
walk-forward validation with dual benchmarks (uniform + hypergeometric).
Results persist as immutable ``bt_*`` snapshots with SHA-256 fingerprinting.
"""
