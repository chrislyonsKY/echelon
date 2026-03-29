# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Public satellite imagery search endpoint (`/api/imagery/search`) for Capella SAR and Maxar open-data catalogs
- Raster analysis endpoint (`/api/imagery/analyze`) for on-demand scene statistics
- Derived vessel and aircraft track endpoint (`/api/signals/tracks`) — groups AIS and OpenSky signal history into GeoJSON LineString features
- Imagery drawer panel in the frontend map UI (`ImageryPanel.tsx`)
- Track line overlays on the map for AIS vessel paths and ADS-B aircraft paths
- CI workflow (GitHub Actions) with frontend type-check/lint and backend compile check
- ESLint configuration for the frontend (`frontend/.eslintrc.cjs`)
- CODE_OF_CONDUCT.md (Contributor Covenant v2.1)
- API endpoint reference table in README

### Changed
- Updated README with imagery, tracks, and API documentation sections
- Updated DEPLOY.md to reflect current service topology
- Updated architecture docs and spec for imagery and track capabilities
- Improved source-health telemetry consistency in health router
- Methodology page updated with imagery and track sections

### Fixed
- Local auth secure-cookie flag preventing login in development
- Source-health `last_run` telemetry returning inconsistent timestamps
- Stale deployment and architecture documentation drift

## [0.1.0] - 2025-03-25

### Added
- Initial project scaffold
- Docker Compose 8-service stack (Nginx, FastAPI, Celery worker/beat/flower, PostGIS, Redis, Frontend)
- CLAUDE.md AI agent entry point
- Architecture, spec, ADR, and guardrail documentation in ai-dev/
- Zustand store skeleton with full type definitions
- Convergence scorer skeleton with signal weights and formula constants
- Celery beat schedule for all ingestion and maintenance tasks
- .env.example with all required variables documented
