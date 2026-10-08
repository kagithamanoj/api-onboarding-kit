# Getting started

## Install

```bash
pip install api-onboarding-kit
```

Or from source:

```bash
git clone https://github.com/kagithamanoj/api-onboarding-kit.git
cd api-onboarding-kit
pip install -e ".[dev]"
```

## The five-minute loop

```bash
# 1. Scaffold a consumer
onboard init payments-team

# 2. Edit payments-team.yaml: contact, traffic, auth, policies

# 3. Validate (schema + lint)
onboard validate payments-team.yaml

# 4. Dry-run: see what would be provisioned
onboard plan payments-team.yaml

# 5. Render gateway config
onboard render payments-team.yaml --gateway aws --out-dir out/

# 6. Check the cost before you commit
onboard cost payments-team.yaml --all
```

## The lifecycle of a consumer

1. **Declare** the consumer in YAML (`onboard init` or `onboard import`).
2. **Validate** locally and in CI (`onboard validate`, `onboard ci-init`).
3. **Simulate** load against the rate limit (`onboard simulate`).
4. **Render** configs and Terraform (`onboard render`).
5. **Promote** through environments (`onboard promote --from staging --to prod`).
6. **Watch** for drift and expiring certs (`onboard diff`, cert checks).

Every step is recorded in the audit ledger (`onboard history`).
