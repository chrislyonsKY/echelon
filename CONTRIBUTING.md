# Contributing to Echelon

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Read `CLAUDE.md` before writing any code — it contains the project conventions
4. Read `ai-dev/guardrails/` — these constraints are non-negotiable
5. Make your changes following the patterns in `ai-dev/architecture.md`
6. Commit using [Conventional Commits](https://www.conventionalcommits.org/): `feat(module): description`
7. Push and open a pull request against `main`

## Development Setup

```bash
git clone https://github.com/chrislyonsKY/echelon.git
cd echelon
cp .env.example .env
# Fill in API keys
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build
```

## Code Standards

- All Python code: async, typed, docstrings, logging (not print), parameterized SQL
- All TypeScript code: no `any`, typed API calls through `src/services/api.ts`, Zustand for state
- No API keys in source files, ever
- See `ai-dev/guardrails/coding-standards.md` for the full ruleset

## Reporting Bugs

Open a GitHub Issue with: clear title, steps to reproduce, expected vs. actual behavior, environment details.

## Security Vulnerabilities

Do not open public Issues for security vulnerabilities. See [SECURITY.md](SECURITY.md).

## Data Attribution

Any contributions involving ACLED, GFW, or other licensed data must maintain attribution requirements as documented in `ai-dev/guardrails/data-handling.md`.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree to uphold its standards.
