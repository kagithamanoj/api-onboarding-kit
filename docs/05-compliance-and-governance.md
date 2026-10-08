# Compliance and governance

## Compliance packs

Select `compliance:pci-dss` or `compliance:soc2` in the spec's policy list.
The validator enforces, on top of the normal rules:

- compliance packs require `oauth2` or `mtls`; `apikey` fails validation.
- compliance plus `prod` requires an `ip-allowlist` policy.

`examples/pci-consumer.yaml` is a complete example.

## Promotion workflow

```bash
onboard promote spec.yaml --from staging --to prod
```

This validates the spec, pre-flight renders every gateway for the target
environment, asks for confirmation, and records the promotion. Promotion
with failing lint findings is refused.

## Audit ledger

Renders, promotions, and CA issuances append to
`.onboarding/ledger.jsonl`:

```bash
onboard history
onboard history --spec payments-team
```

## Drift detection

```bash
onboard diff spec.yaml --gateway aws --deployed ./deployed/
```

Unified diffs for anything missing or changed. Non-zero exit on drift, so
it gates CI pipelines.
