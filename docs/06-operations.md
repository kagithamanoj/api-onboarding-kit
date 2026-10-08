# Operations: certificates, cost, simulation

## Private CA

For internal mTLS, run your own CA:

```bash
onboard ca-init --cn "Example Internal CA" --out certs/
onboard ca-issue --ca certs/ --domain api.internal.example.com --out out/
onboard ca-crl --ca certs/
```

The CA key is created with `0600` permissions. Protect the `certs/`
directory like production credentials. Revocation is tracked and published
via CRL.

For dev and staging without a CA, `generate_dev_cert()` in
`onboarding/certs.py` issues self-signed certificates. Never use those in
production; the validator cannot tell the difference, so make it policy.

## Cost estimation

```bash
onboard cost spec.yaml --all
```

Estimates monthly gateway cost from the traffic profile across clouds and
tiers. Directional, from public list pricing. Verify before budgeting.

## Traffic simulation

```bash
onboard simulate spec.yaml --rps 500 --duration 60
```

Models the resolved rate-limit policy as a token bucket and replays the
offered load. Tells you how many requests would see a 429 before you find
out in production. A model, not a measurement.

## Backstage

```bash
onboard catalog spec.yaml --out catalog-info.yaml
```

Registers the consumer in the Backstage service catalog as an API entity.
