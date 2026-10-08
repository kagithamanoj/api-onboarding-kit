# Multi-cloud rendering

One spec renders to four clouds. Pick with `--gateway`, pick the output
kind with `--format`.

| gateway | native output | terraform output |
|---------|---------------|------------------|
| `apim` | Azure APIM policy XML | `azurerm` API, product, subscription, policy |
| `apigee` | Apigee proxy bundle XML | roadmap |
| `gcp` | API Gateway OpenAPI config | `google_api_gateway_*` resources |
| `aws` | API Gateway OpenAPI + usage plan | `aws_api_gateway_*` resources |

The Terraform output references the native files (`file(...)`,
`filebase64(...)`), so the gateway config and the infrastructure that
deploys it come from the same spec and cannot drift apart at the source.

```bash
onboard render spec.yaml --gateway aws --format terraform --out-dir tf/
```

## Environment-aware rendering

With `--env`, overlays apply before rendering: the backend address,
traffic profile, and policy list reflect that stage.

```bash
onboard render spec.yaml --gateway gcp --env prod --out-dir out/prod/
```
