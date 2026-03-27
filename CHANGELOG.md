# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

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
