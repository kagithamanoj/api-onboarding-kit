# Policy library

`policies/library.yaml` is the single source of truth for gateway behavior.
Each entry has a `type`, a `description`, and an `owner`. Bump `version`
on every change; changes are reviewed like code.

## Individual policies

| ref | type | what it does |
|-----|------|--------------|
| `rate-limit:standard` | rate-limit | 1000 calls / 60s per key |
| `rate-limit:high-throughput` | rate-limit | 10000 calls / 60s per key |
| `cors:default` | cors | standard browser CORS |
| `auth:jwt-required` | auth | JWT on every request |
| `ip-allowlist:office` | ip-allowlist | office egress ranges |

## Bundles

A bundle expands into member policies at render time. Selecting
`compliance:pci-dss` is equivalent to selecting its three members, and
selecting both a bundle and one of its members still renders each policy
once.

| ref | members |
|-----|---------|
| `compliance:pci-dss` | auth:jwt-required, rate-limit:standard, ip-allowlist:office |
| `compliance:soc2` | auth:jwt-required, rate-limit:standard |

## Adding a policy

1. Add it to `policies/library.yaml` with an owner.
2. Bump the library `version`.
3. If the gateway templates need to understand the new `type`, extend them.
4. Add a test. The validator suite is the contract.
