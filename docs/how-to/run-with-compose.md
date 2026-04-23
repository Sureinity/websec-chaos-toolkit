# Run The Toolkit With Docker Compose

This guide documents the checked-in Docker Compose topology and its current
limits. The repository includes Compose assets for the preferred Docker-first
operator story, but the automated coverage for this path is static-contract
only in `tests/integration/test_compose_workflow.py`; it does not build a
packaged runner image or execute an end-to-end Compose smoke test.

## Why Compose

Docker Compose lets operators model the toolkit runner, an example target app,
and an optional Toxiproxy service together as one declarative service graph.
Benefits over direct CLI use:

- no scanner binaries need to be installed directly on the host to define the
  topology
- service-name DNS for predictable target reachability
- portable across CI, staging boxes, and operator workstations
- a single `docker compose up` brings the whole environment online

Direct CLI usage and `--runtime host` mode remain supported as fallback
paths for environments where Docker Compose is not available.

## Before You Start

- Docker Engine 20.10+ and Docker Compose v2 installed
- Repository checked out locally
- A live target service to scan (the example uses an `nginx:alpine`
  placeholder; replace with your real app image when wiring a project)
- Awareness that the checked-in `toolkit-runner` service uses
  `python:3.13-slim`, mounts the source tree, and sleeps; it defines the
  workspace contract but is not a prebuilt toolkit image

Verify Compose is available:

```bash
docker compose version
```

## Repository Layout

```
docker-compose.yml                       # the Compose file
compose/toolkit-runner.env.example       # env template for the runner
examples/configs/sample-webapp/          # mounted as /workspace/config
examples/configs/sample-webapp-compose/  # Compose-aware config alternative
compose/examples/sample-webapp-compose/  # sample overlay for the Compose-aware config
outputs/                                 # mounted as /workspace/outputs
```

## Operator Modes

### Pentest only

Brings up the toolkit runner and the target app:

```bash
docker compose up -d toolkit-runner sample-app
```

The checked-in `docker-compose.yml` reads
`compose/toolkit-runner.env.example` directly via `env_file`. If you prefer a
private local copy such as `compose/toolkit-runner.env`, update the `env_file`
entry before starting the stack.

### Pentest + chaos

Adds the optional Toxiproxy service for live chaos experiments:

```bash
docker compose --profile chaos up -d toolkit-runner sample-app toxiproxy
```

The Toxiproxy service is gated behind the `chaos` profile so pentest-only
operators do not pull the image unnecessarily.

## Running Toolkit Commands

The checked-in Compose file defines the working directory, mounts, and
service-name networking. It does not install the toolkit automatically inside
`toolkit-runner`. After you replace the placeholder image or bootstrap the
container so the `toolkit` CLI is available, these are the intended operator
commands:

```bash
docker compose exec toolkit-runner toolkit validate \
  --app sample-internal-app --env local
```

```bash
docker compose exec toolkit-runner toolkit pentest run \
  --app sample-internal-app --env local --profile safe-web-baseline \
  --runtime container
```

```bash
docker compose exec toolkit-runner toolkit chaos run \
  --app sample-internal-app --env local --profile dependency-latency-baseline
```

The runner's working directory is `/workspace`. The mounted config bundle
lives at `/workspace/config` and run artifacts are written to
`/workspace/outputs`, which maps to `./outputs` on the host.

## Service Networking

All services join the `toolkit-net` bridge network. They resolve each
other by service name:

| From | To | Address |
|------|----|---------|
| toolkit-runner | sample-app | `http://sample-app:8080` |
| toolkit-runner | toxiproxy | `http://toxiproxy:8474` |

The example `apps.yaml` sets `base_url: http://sample-app:8080` so the
toolkit runner reaches the target app on the shared network without
relying on `--network=host`.

## Mounted Volumes

| Host path | Container path | Mode | Purpose |
|-----------|---------------|------|---------|
| `examples/configs/sample-webapp` | `/workspace/config` | read-only | YAML config bundle |
| `outputs/` | `/workspace/outputs` | read-write | run artifacts |
| `src/` | `/workspace/src` | read-only | toolkit source |
| `pyproject.toml` | `/workspace/pyproject.toml` | read-only | package metadata |
| `uv.lock` | `/workspace/uv.lock` | read-only | locked dependency set |

## Intended Pentest Command Shape

Once the runner environment has been bootstrapped inside the container, the
intended pentest command shape is:

```bash
docker compose exec toolkit-runner toolkit pentest run \
  --app sample-internal-app \
  --env local \
  --profile safe-web-baseline \
  --runtime container
```

The checked-in assets guarantee the mounted workspace layout and service-name
networking for that command shape. They do not yet prove an end-to-end runner
image, Docker socket wiring, or in-container dependency bootstrap.

Environment variables referenced by the checked-in Compose assets:

- `SAMPLE_API_BEARER_TOKEN` — only needed when running the sample-api pack
- `NUCLEI_DISABLE_UPDATE_CHECK=true` — recommended for deterministic runs
- `TOOLKIT_TOXIPROXY_URL=http://toxiproxy:8474` — used by chaos workflows on
  the shared Compose network

## Intended Chaos Command Shape

Bring up the chaos profile (which includes Toxiproxy):

```bash
docker compose --profile chaos up -d toolkit-runner sample-app toxiproxy
```

Wait for Toxiproxy to be reachable, then create a proxy for the target:

```bash
docker compose exec toxiproxy /toxiproxy-cli create \
  --listen 0.0.0.0:19000 \
  --upstream sample-app:8080 \
  sample-app
```

After the runner environment has been bootstrapped inside the container, the
intended chaos command shape is:

```bash
docker compose exec \
  -e TOOLKIT_TOXIPROXY_URL=http://toxiproxy:8474 \
  toolkit-runner toolkit chaos run \
  --app sample-internal-app \
  --env local \
  --profile dependency-latency-baseline
```

Startup order matters for chaos:

1. `sample-app` must be healthy before `toxiproxy` proxies traffic to it
2. `toxiproxy` must be running before the toolkit attempts proxy creation
3. The toolkit container reaches Toxiproxy via service-name DNS at
   `http://toxiproxy:8474`

## Shared Outputs And Report Rebuild

All run artifacts under `/workspace/outputs/` persist to `./outputs/` on
the host. After a pentest or chaos run, you can rebuild the executive
summary from any earlier run, once the runner container has the `toolkit` CLI
available:

```bash
docker compose exec toolkit-runner toolkit report build --run-id <run-id>
```

The same `outputs/` directory is shared across runs, so a host-side
`uv run toolkit report build --run-id <run-id>` works against artifacts
created by the Compose runner.

## Stopping

```bash
docker compose down
```

To remove the persistent outputs directory volume, also pass `-v`:

```bash
docker compose down -v
```

## Fallback: Direct CLI

If Compose is not available, the same workflow runs directly on the host
with `uv run toolkit ...`. See:

- `docs/how-to/run-live-pentest.md`
- `docs/how-to/run-live-chaos.md`

## Current Limitations

- the repository does not currently ship a built `toolkit-runner` image
- the checked-in Compose coverage is static-contract only, not end-to-end
- `docker-compose.yml` currently points `env_file` at
  `compose/toolkit-runner.env.example`
- chaos workflows still require explicit proxy creation before
  `toolkit chaos run`

## See Also

- `docs/explanation/compose-workflow-model.md` — service topology rationale
- `docs/explanation/container-runtime-model.md` — Docker runtime backend
- `docs/reference/cli.md` — command reference
