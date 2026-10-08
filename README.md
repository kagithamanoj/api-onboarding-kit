# api-onboarding-kit

**Self-service API consumer onboarding for multi-tenant platforms. Multi-cloud: Azure, GCP, AWS.**

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

Onboarding a new API consumer used to take days: tickets, hand-edited gateway configs, certificate requests bouncing between teams, and a final round of "it works on my machine." This kit collapses that into a single declaration. A consumer describes what it needs in YAML. The kit validates it, renders versioned gateway configuration and Terraform, estimates cost, checks drift, and tracks certificate lifecycles. The same checks run on a laptop and in CI.

## The idea

Two consumers with identical requirements should get byte-identical infrastructure. That only happens when no human hand-edits the config. So:

- **Declare, don't ticket.** One YAML file per consumer: identity, traffic, auth, policies, certificates.
- **Templates, not snowflakes.** Gateway configs render from versioned Jinja2 templates. Customization happens through parameters, never free-text edits.
- **Policy as a library.** Rate limits, CORS, auth, IP rules, and compliance bundles live in one versioned file with owners. Onboarding selects policies; it never authors them inline.
- **Certificates as a lifecycle.** Expiry tracking and renewal hooks from day one, not as an afterthought after the first outage.
- **CI is the gate.** Schema validation, lint rules, and dry-run rendering run everywhere. If it passes locally, it passes in the pipeline.

```
consumer.yaml ──> validate ──> render ──> apim / apigee / gcp / aws (+ terraform)
                         │                + backstage catalog
                         ├──> plan        dry-run summary (per-env with --env)
                         ├──> cost        monthly estimate per cloud
                         ├──> simulate    load vs rate limit (token bucket)
                         ├──> diff        drift vs deployed files
                         ├──> promote     staging -> prod with pre-flight checks
                         ├──> history     audit ledger of every action
                         └──> certs       private CA, expiry tracking, CRLs
```

## Quickstart

```bash
git clone https://github.com/kagithamanoj/api-onboarding-kit.git
cd api-onboarding-kit
pip install -e ".[dev]"
```

Scaffold a consumer, validate it, see what would be provisioned:

```bash
onboard init payments-team
# edit payments-team.yaml, then:
onboard validate payments-team.yaml
onboard plan payments-team.yaml
onboard render payments-team.yaml --gateway apim --out-dir out/
```

Or try the included example:

```bash
onboard plan examples/consumer.yaml
onboard render examples/consumer.yaml --gateway apigee --out-dir out/
```

## What it generates

One spec, four clouds, two formats:

- **Azure APIM** (`--gateway apim`): policy XML with rate limiting, CORS, JWT validation, IP filtering, composed from the policy library. `--format terraform` adds the `azurerm` resources that deploy the API, product, subscription, and attach the policy.
- **Apigee** (`--gateway apigee`): proxy bundle with endpoint, route rules, and target definitions per consumer.
- **Google Cloud API Gateway** (`--gateway gcp`): OpenAPI service config with backend routing, quota limits, and metrics. `--format terraform` adds the `google_api_gateway_*` resources.
- **AWS API Gateway** (`--gateway aws`): OpenAPI with integration extensions plus a usage plan carrying throttle and quota. `--format terraform` adds the `aws_api_gateway_*` resources.

The Terraform output references the native files (`file(...)` / `filebase64(...)`), so config and infrastructure stay in one pipeline. Every file is stamped with the spec name and policy library version and says "Do not hand-edit: regenerate from the consumer spec."

## Promotion workflow

```bash
onboard promote specs/payments.yaml --from staging --to prod
```

Validates the spec, pre-flight renders every gateway for the target
environment (environment overlays applied), asks for confirmation, and
records the promotion in the audit ledger. Promotion with failing lint
findings is refused. See `docs/02-spec-reference.md` for overlays.

## Private CA and certificates

```bash
onboard ca-init --cn "Example Internal CA" --out certs/
onboard ca-issue --ca certs/ --domain api.internal.example.com --out out/
onboard ca-crl --ca certs/
```

A real private CA for internal mTLS: 4096-bit root, per-service issuance,
revocation tracking, CRL publishing. The CA key is created with `0600`
permissions. For dev without a CA, self-signed certs are available in
`onboarding/certs.py` (never for production).

## Traffic simulation

```bash
onboard simulate specs/payments.yaml --rps 500 --duration 60
```

Models the resolved rate-limit policy as a token bucket and replays the
offered load: allowed requests, rejected 429s, and a verdict. Answers
"will this rate limit survive the launch?" before production does.

## Audit ledger and Backstage

```bash
onboard history --spec payments-team
onboard catalog specs/payments.yaml --out catalog-info.yaml
```

Every render, promotion, and issuance is appended to
`.onboarding/ledger.jsonl`. The catalog command registers the consumer in
Backstage as an API entity.

## Brownfield: import from OpenAPI

Teams that already have APIs do not start from a blank spec:

```bash
onboard import ./inventory-openapi.yaml --out specs/inventory.yaml
```

This infers the consumer name, auth model (OAuth2, API key, mTLS), and endpoint count, fills safe defaults for traffic, and marks everything it guessed in `x-imported` so a human reviews it. See `examples/openapi-sample.yaml`.

## Cost estimation

```bash
onboard cost specs/payments.yaml --all
```

Estimates monthly gateway cost from the spec's traffic profile across clouds and tiers, cheapest first. Directional only, from public list pricing. Useful for tier selection and for the "which cloud?" conversation with finance. It will happily tell you that serverless tiers win at low traffic and fixed tiers win at scale, because the math says so.

## Compliance packs

```yaml
policies:
  - compliance:pci-dss
```

Bundles expand into member policies at render time (`compliance:pci-dss` becomes JWT auth, standard rate limiting, and the office IP allowlist). The validator adds compliance rules on top: no API-key auth under a compliance pack, and prod plus compliance requires an IP allowlist. See `examples/pci-consumer.yaml`.

## Drift detection

```bash
onboard diff specs/payments.yaml --gateway aws --deployed ./deployed/
```

Compares rendered output against the deployed files and prints unified diffs for anything missing or changed. File-based on purpose: it runs in CI with no cloud credentials, and drift becomes reviewable text. Exit code is non-zero when drift exists, so it gates pipelines.

## CI in one command

```bash
onboard ci-init
```

Writes a GitHub Actions workflow that validates every spec under `specs/` and render-checks all gateways on each pull request.

## Lint rules

The validator enforces the boring things humans forget:

- Every consumer must select a rate-limit policy.
- API-key auth in prod is flagged; prefer OAuth2 or mTLS.
- Certificates without auto-renew are flagged before they become outages.
- Compliance packs require OAuth2 or mTLS, and prod plus compliance requires an IP allowlist.
- Unknown policies, environments, and auth methods fail the schema.

Run `onboard validate` locally or wire it into CI. Same checks, same result.

## Project structure

```
api-onboarding-kit/
  onboarding/      spec, policies, renderer, validator, certs (private CA),
                   importer, cost, drift, ledger, simulate, catalog, cli
  templates/       Jinja2 templates per gateway (apim, apigee, gcp, aws)
                   plus terraform/, ci/, backstage/
  policies/        versioned policy library (library.yaml)
  examples/        consumer spec (with env overlays), PCI example, OpenAPI sample
  docs/            six-chapter user guide
  tests/           pytest suite (62 tests)
```

## Roadmap

- Live-state drift detection via cloud APIs (Azure, AWS, GCP read-only)
- ACME integration for public certificate issuance
- Apigee Terraform output
- Canary rollouts for policy changes
- OpenAPI operation-level import (per-path gateway config)

## License

MIT. See LICENSE.

---

*Built clean-room from onboarding automation patterns for multi-tenant API platforms. No proprietary code, no customer data, no employer IP: just the patterns, rebuilt from scratch.*
