# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x (latest) | ✅ |

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub Issues.**

To report a vulnerability:

1. Email **security@chrislyons.dev** with the subject line:
   `[Security] Echelon — brief description`
2. Include:
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested mitigations (optional)

You will receive an acknowledgment within **72 hours**. We aim to triage and respond with a timeline within **7 days**.

## Disclosure Policy

We follow [responsible disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure). Please allow reasonable time to patch before public disclosure.

## Scope

**In scope:**
- Vulnerabilities in Echelon source code
- BYOK API key handling or storage flaws
- Session token exposure
- SQL injection or parameterization bypasses
- Dependency vulnerabilities introduced by this project's configuration

**Out of scope:**
- Vulnerabilities in upstream dependencies (report directly to the upstream maintainer)
- Issues in development/test tooling not shipped with the project
- Issues requiring physical access to the deployment server

## Security Updates

Security fixes are documented in [CHANGELOG.md](CHANGELOG.md) under the `### Security` heading.
