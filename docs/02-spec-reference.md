# Spec reference

```yaml
apiVersion: onboarding/v1
consumer:
  name: payments-team          # required, DNS-compatible
  contact: team@example.com    # required
  environments: [dev, staging, prod]   # list form, or mapping form below
traffic:
  expectedRps: 200             # required, > 0
  burstRps: 500                # required, >= expectedRps
auth:
  method: oauth2               # oauth2 | apikey | mtls
policies:                      # refs into policies/library.yaml
  - rate-limit:standard
  - cors:default
  - auth:jwt-required
certificates:
  domains: [api.example.com]   # optional
  autoRenew: true              # default true
```

## Environment overlays

When stages differ, use the mapping form. Overlay keys: `backend`,
`expectedRps`, `burstRps`, `policies` (replaces the list).

```yaml
consumer:
  name: payments-team
  environments:
    dev:
      backend: https://payments.dev.internal
    staging:
      backend: https://payments.staging.internal
    prod:
      backend: https://payments.prod.internal
      expectedRps: 2000
      burstRps: 2500
```

Render for one environment with `onboard render spec.yaml --env prod`.
Promote between stages with `onboard promote spec.yaml --from staging --to prod`.
