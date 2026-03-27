# DL-005: GDELT as Scoring-Only Signal (Not UI-Visible Articles)

**Date:** 2025-03-25
**Status:** Accepted
**Author:** Chris Lyons

## Context

GDELT publishes machine-coded conflict events every 15 minutes from global news sources using CAMEO event codes. It provides geographic precision (lat/lon of the event, not the publication) and multilingual coverage. However, GDELT events are raw machine codes — not human-readable articles.

NewsData.io provides human-readable articles with headline and description, but has a 12-hour delay on the free tier and a higher noise ratio.

## Decision

Use GDELT exclusively in the convergence scoring pipeline (signal source = 'gdelt', weight = 0.12) and surface it only as a contributor to Z-scores. Use NewsData.io for the human-readable news sidebar in the investigation sidebar UI. GNews serves as a fallback for NewsData.

GDELT's geographic precision and zero-delay make it the better scoring signal. NewsData's human readability makes it the better UI signal. They serve different roles.

## Consequences

- GDELT events are never shown as article cards in the Signal Cards tab.
- Users will see GDELT contribution in the signal_breakdown JSON of a convergence cell but not as named articles.
- The GDELT ingestion task must filter to CAMEO codes 19x and 20x only — full GDELT ingestion would overwhelm the signals table.
