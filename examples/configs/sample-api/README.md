# Sample API Config Pack

This config pack is the sanitized authenticated API variant for operator docs
and later smoke coverage.

Safe usage:

- app id: `sample-api-bearer-app`
- environment: `staging`
- auth method: `bearer_token`
- enabled modules: `pentest`

Secrets remain out of YAML. Set the bearer token in the runtime environment
before using authenticated commands:

```bash
export SAMPLE_API_BEARER_TOKEN=placeholder-token
uv run toolkit validate --app sample-api-bearer-app --env staging
```
