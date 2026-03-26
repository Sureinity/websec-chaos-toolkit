# Configuration Reference

The bootstrap scaffold includes placeholder repository-level configuration
files:

- `apps.yaml`
- `pentest-profiles.yaml`
- `chaos-profiles.yaml`

These files exist to anchor the intended user-facing surface. Full validation
and operational semantics are still pending.

Minimum intended data shape:

- `apps.yaml`: app id, environment, base URL, host targets, target allowlist,
  auth method, health endpoint, optional metrics source, enabled modules
- `pentest-profiles.yaml`: tool enablement, safe profile selection, allowlisted
  rules or templates, schedule labels
- `chaos-profiles.yaml`: fault type, target service, baseline duration,
  experiment duration, abort thresholds, rollback method
