# Governance

## Project Direction

Echelon is maintained as a focused GEOINT/OSINT project. The repository is not intended to become a general-purpose surveillance platform or an unbounded intelligence connector bundle.

Maintainers reserve the right to reject features that conflict with:

- lawful and responsible-use boundaries
- source licensing or attribution requirements
- clear provenance standards
- maintainability of the current architecture

## Maintainer Responsibilities

Maintainers are expected to:

- review contributions for correctness, security, and provenance implications
- preserve project guardrails around responsible use
- avoid merging features that encourage unlawful surveillance, offensive targeting, or misleading confidence claims
- keep deployment and security documentation aligned with the runtime where practical

## Contribution Decision Criteria

Changes are more likely to be accepted when they:

- improve analyst clarity
- improve source provenance, attribution, or confidence labeling
- improve security, reliability, or deployment safety
- fit the current architecture
- include enough testing or validation to be reviewed responsibly

Changes are less likely to be accepted when they:

- weaken provenance or attribution handling
- add sources without clear licensing review
- create avoidable security risk
- expand the project toward harmful or invasive use cases

## Source Additions

New data sources should not be added casually. A source addition should usually include:

- a provenance-family decision
- a confirmation-policy decision
- attribution and license review
- health telemetry
- an explanation of whether the source is scoreable, analyst-only, or context-only

## Policy Changes

Changes to security, responsible-use, provenance, or conduct policies should be treated as maintainership-level changes, not casual drive-by edits.
