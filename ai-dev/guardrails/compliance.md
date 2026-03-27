# Compliance Guardrails

---

## WCAG 2.1 Level AA (Frontend)

All UI components must meet WCAG 2.1 Level AA. Violations are blockers for any PR.

- All interactive elements (buttons, links, inputs, checkboxes) must have accessible names via `aria-label`, `aria-labelledby`, or visible label text
- Color must NEVER be the sole means of conveying information — applies critically to:
  - The convergence heatmap (low-confidence cells must use pattern + color, not color alone)
  - Signal type indicators in Signal Cards (use icon or text label alongside color)
  - Z-score badges (include numeric value, not just color)
- Minimum contrast ratio: 4.5:1 for normal text, 3:1 for large text and UI components
- All keyboard interactions must be functional: map cell selection, sidebar tab navigation, copilot input
- Focus indicators must be visible (`:focus-visible` style defined in index.css)
- The investigation sidebar must trap focus when open and release on close
- Screen reader announcements for dynamic content updates (convergence refresh, new alerts)

## Data Attribution (Legal)

ACLED End User License Agreement requires explicit attribution wherever ACLED data is displayed:
> "Data sourced from ACLED (Armed Conflict Location & Event Data Project) — acleddata.com"

This must appear in:
- Signal Cards displaying ACLED events
- The map data sources panel
- The README and any public documentation

GFW requires attribution:
> "Vessel data from Global Fishing Watch — globalfishingwatch.org"

NGA LandScan is now free without restrictions but attribution is courteous:
> "Population data: LandScan™ — Oak Ridge National Laboratory / NGA"

## Open Source License Compliance

All dependencies must be compatible with Apache 2.0. Check before adding new packages:
- MIT, BSD, ISC, Apache 2.0 → compatible
- LGPL → compatible with conditions (dynamic linking)
- GPL → incompatible — do NOT add GPL dependencies
- AGPL → incompatible — do NOT add AGPL dependencies

Note: `rasterio` is MIT. `h3` is Apache 2.0. `geoalchemy2` is MIT. All clear.

## API Terms of Service

- **GFW**: Free for non-commercial use. Echelon is open-source and non-commercial — compliant. If ever monetized, contact GFW for commercial license.
- **GDELT**: Fully open, no restrictions.
- **Overpass API**: Free with rate limiting. Must throttle requests — see data-handling.md.
- **ACLED**: Attribution required. Redistribution of raw data prohibited — Echelon stores derived signals, not raw exports. Compliant.
- **NewsData.io**: Free tier is labeled as permitted for commercial use. Paid tier required above 200 credits/day.
