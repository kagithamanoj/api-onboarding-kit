# Changelog

## 1.0.0 (2026-10-08)

First stable release. The complete onboarding lifecycle in one CLI:

- Environment overlays and promotion: per-stage backends, traffic, and
  policies; `onboard promote --from staging --to prod` with pre-flight
  checks and confirmation.
- Private certificate authority: `ca-init`, `ca-issue`, `ca-crl`,
  revocation tracking, 4096-bit CA keys.
- Audit ledger: renders, promotions, and issuances recorded;
  `onboard history`.
- Traffic simulator: token-bucket model of the rate-limit policy;
  `onboard simulate --rps 500`.
- Backstage catalog generation: `onboard catalog`.
- `docs/` user guides (six chapters).
- 62 tests passing.

## 0.3.0 (2026-10-08)

- Terraform output for Azure APIM, AWS, and GCP.
- OpenAPI import: `onboard import` generates a starter spec.
- Cost estimation: `onboard cost --all` compares clouds and tiers.
- Compliance bundles (`compliance:pci-dss`, `compliance:soc2`) with
  validator rules.
- File-based drift detection: `onboard diff`.
- GitHub Actions CI generator: `onboard ci-init`.
- 44 tests passing.

## 0.2.0 (2026-10-08)

- Multi-cloud renderers: Azure APIM, Apigee, GCP API Gateway,
  AWS API Gateway (OpenAPI + usage plan).
- Versioned policy library, CI lint rules, certificate lifecycle,
  click CLI. 19 tests passing.

## 0.1.0 (2026-10-08)

- Initial release: spec format, Azure APIM and Apigee renderers,
  validator, dev certificate helpers.
