# Evidence Policy

## Purpose

Echelon may display links, metadata, imagery, and other evidence connected to signals or event rollups. This document defines how evidence should be treated in the project.

## Core Principles

- Evidence is supporting material, not automatic confirmation.
- Provenance must remain visible.
- Graphic, extremist, or manipulative material must be handled deliberately.
- Analyst convenience must not override legal, ethical, or safety concerns.

## Evidence Categories

Evidence may include:

- imagery scenes
- video links
- image links
- documents
- source articles
- analyst-added context links

Each item should retain its source URL, type, and provenance fields where possible.

## Graphic or Disturbing Content

When evidence may be graphic:

- default to restrained presentation
- preserve review status and moderation metadata
- avoid surprise exposure in general UI views
- prefer explicit analyst action before opening clearly graphic material

## Extremist or Harmful Propaganda

Do not treat propaganda material as ordinary evidence. If it is retained for documentation or contextual analysis:

- label it clearly
- avoid promotional presentation
- avoid unnecessary reproduction or embedding
- preserve analyst warnings where appropriate

## Verification

Evidence must not be described as verified unless that status is actually supported by the workflow. In practice:

- source presence is not verification
- geolocation claims require corroboration
- time verification claims require corroboration
- AI interpretation is not verification

## Takedowns and Removal

If a legitimate removal, legal, or safety concern is raised, maintainers may remove or restrict evidence links or metadata from the project spaces even if the underlying content exists elsewhere.

## Exports

If evidence metadata is exported, exports should preserve:

- source URL
- type
- provenance family
- confirmation policy
- review or moderation status where available

## Contributor Guidance

Contributors should avoid adding evidence-handling features that:

- auto-expand disturbing content
- suppress provenance or warnings
- overstate confidence
- make extremist or violent material more discoverable than necessary
