# Testing

## Purpose

This document describes the current expected validation workflow for Echelon changes.

Because this project mixes frontend UI, backend APIs, scheduled ingest tasks, and external-source parsing, "it builds" is not enough.

## Baseline Checks

For normal code changes, run:

```bash
python3 -m compileall backend/app
cd frontend && npm run type-check
cd frontend && npm run lint
```

These are the current minimum local checks and align with the repository CI baseline.

## Changes That Need More Than Baseline

### Backend API or Router Changes

Also verify:

- route behavior locally through the running stack
- error handling for invalid input
- no obvious secret leakage in logs or tracebacks

### Ingest or Parser Changes

Also verify:

- expected source-health updates
- safe behavior on empty, malformed, or slow upstream responses
- no duplicate or broken signal insertion behavior

### Frontend Map Changes

Also verify:

- overlays render at expected zoom levels
- popups still work
- no obvious regression on mobile and desktop viewport sizes
- expensive layers do not load too early

### Deployment or Environment Changes

Also verify:

- Docker build still works
- migrations still run
- auth and cookies behave correctly behind the target proxy

## Manual Verification Suggestions

Useful manual checks include:

- login flow
- saved AOI flow
- alert management
- source-health panel
- event detail and evidence display
- exports
- imagery search and analysis routes
- track overlays for AIS and OpenSky

## Test Design Priorities

If automated tests are expanded, prioritize:

1. parser and source-normalization tests
2. router validation and response-shape tests
3. scoring and provenance logic tests
4. security-sensitive auth and cookie behavior
5. map overlay regression coverage where practical

## Known Gaps

The project currently relies heavily on compile, lint, and manual verification. That is acceptable for early-stage iteration, but not sufficient long term for a repo with external ingest pipelines and security-sensitive auth flows.
