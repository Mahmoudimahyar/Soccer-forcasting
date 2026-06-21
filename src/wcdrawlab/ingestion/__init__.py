"""Read-only data-ingestion scaffolding (Data Enrichment Gate 1).

Scope (enforced by design): provider health checks, append-only raw snapshot storage, schema +
normalized-record validation, provenance capture, reconciliation, and DRY-RUN ingestion only.

This package does NOT trade, poll markets, place bets, scrape, bypass robots/terms/rate-limits,
or run model experiments. No secret values are read into any returned object, log, or file.
"""
