# Sample Web App Config Pack

This config pack is the default sanitized example for local validation,
fixture-backed pentest runs, fixture-backed chaos runs, and report rebuilds.

Safe usage:

- app id: `sample-internal-app`
- environment: `local`
- auth method: `none`
- enabled modules: `pentest`, `chaos`

Useful commands from this directory:

```bash
uv run toolkit validate --app sample-internal-app --env local
uv run toolkit pentest run --app sample-internal-app --env local --profile safe-web-baseline
uv run toolkit chaos run --app sample-internal-app --env local --profile dependency-latency-baseline
```
