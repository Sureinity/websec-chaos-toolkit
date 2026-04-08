# sample-webapp-compose Example Topology

This directory holds Compose overlays and assets for the
`examples/configs/sample-webapp-compose/` config pack.

## What This Demonstrates

- a target app reachable by service name (`sample-app`)
- the toolkit-runner on the same `toolkit-net` network
- optional Toxiproxy service available via the `chaos` profile
- mapping from Compose service names to `apps.yaml` `base_url` values

## Service Mapping

| Compose service | apps.yaml reference |
|----|----|
| `toolkit-runner` | (the runner; not a target) |
| `sample-app` | `base_url: http://sample-app:8080` |
| `toxiproxy` | `target_service: sample-app` (proxy name on Toxiproxy) |

## Files

- `docker-compose.override.yml` — overlay that mounts the
  `sample-webapp-compose` config pack into the toolkit-runner

## See Also

- `examples/configs/sample-webapp-compose/README.md` — config pack readme
- `docs/explanation/compose-workflow-model.md` — topology rationale
