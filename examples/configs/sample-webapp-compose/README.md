# Sample Webapp Compose Config Pack

A Compose-aware variant of `sample-webapp/` for use with the toolkit
runner Compose service.

## Differences from `sample-webapp/`

- `apps.yaml` uses `http://sample-app:8080` (Compose service name) as
  `base_url` instead of `http://localhost:8000`
- `host_targets` and `target_allowlist` include the `sample-app`
  service hostname
- `chaos-profiles.yaml` references `target_service: sample-app` so the
  Toxiproxy proxy name aligns with the Compose service name

## Usage

Mount this directory as `/workspace/config` in the toolkit-runner
container. The default `docker-compose.yml` mounts
`examples/configs/sample-webapp/` by default; override with:

```bash
docker compose run --rm \
  -v $(pwd)/examples/configs/sample-webapp-compose:/workspace/config:ro \
  toolkit-runner toolkit validate \
  --app sample-internal-app --env local
```

Or change the volume mount in `docker-compose.yml` to point at this
directory permanently.

## See Also

- `docs/how-to/run-with-compose.md` — operator workflow
- `docs/explanation/compose-workflow-model.md` — service topology rationale
- `compose/examples/sample-webapp-compose/` — example Compose overlay
