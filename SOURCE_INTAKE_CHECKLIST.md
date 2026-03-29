# Source Intake Checklist

Use this checklist before adding a new data source, parser, feed, or imagery provider to Echelon.

## Source Overview

- Source name:
- Source URL:
- Maintainer / provider:
- Access method: API / RSS / HTML scrape / STAC / WebSocket / file download
- Intended use: scored signal / analyst-only / context-only

## Legal and Attribution

- License or terms reviewed
- Attribution requirements identified
- Redistribution limits identified
- Commercial or non-commercial restrictions identified
- [ATTRIBUTION.md](ATTRIBUTION.md) updated

## Provenance and Confidence

- Provenance family assigned
- Confirmation policy assigned
- Signal semantics documented
- [DATA_PROVENANCE.md](DATA_PROVENANCE.md) updated if needed

## Security and Safety

- Remote fetch behavior reviewed for SSRF or unsafe URL expansion
- Parser handles malformed input safely
- Response size / timeout expectations considered
- Harmful or extremist-content risk considered
- Privacy impact considered if personal data may appear

## Engineering

- Health telemetry added
- Error handling added
- Deduplication strategy defined
- Source identifier strategy defined
- Retention implications considered
- Export implications considered

## Product Fit

- Clear reason this source belongs in Echelon
- Signal adds meaningful analyst value
- Does not duplicate an existing source without justification
- UI implications reviewed if analyst-facing

## Validation

- Happy-path sample tested
- Empty-path sample tested
- Failure-path sample tested
- Local verification steps documented

## Approval

- Maintainer review complete
- Documentation updated
- README or methodology updated if user-facing
