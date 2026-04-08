# Run The Toolkit With Docker Compose

This guide is the preferred Docker-first operator path for running the
internal security toolkit. It defines a portable service topology that
works on any Linux host with Docker Compose installed.

## Why Compose

Docker Compose lets operators run the toolkit, an example target app, and
an optional Toxiproxy service together as one declarative service graph.
Benefits over direct CLI use:

- no scanner binaries needed on the host
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

Verify Compose is available:

```bash
docker compose version
```

## Repository Layout

```
docker-compose.yml                       # the Compose file
compose/toolkit-runner.env.example       # env template for the runner
examples/configs/sample-webapp/          # mounted as /workspace/config
outputs/                                 # mounted as /workspace/outputs
```

## Operator Modes

### Pentest only

Brings up the toolkit runner and the target app:

```bash
cp compose/toolkit-runner.env.example compose/toolkit-runner.env
# edit compose/toolkit-runner.env if you need real secret references

docker compose up -d toolkit-runner sample-app
```

### Pentest + chaos

Adds the optional Toxiproxy service for live chaos experiments:

```bash
docker compose --profile chaos up -d toolkit-runner sample-app toxiproxy
```

The Toxiproxy service is gated behind the `chaos` profile so pentest-only
operators do not pull the image unnecessarily.

## Running Toolkit Commands

Operators exec into the running `toolkit-runner` container to invoke
toolkit commands:

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
| `pyproject.toml` | `/workspace/pyproject.toml` | read-only | dependencies |

## Live Pentest Through Compose

Once `toolkit-runner` and `sample-app` are up:

```bash
docker compose exec toolkit-runner toolkit pentest run \
  --app sample-internal-app \
  --env local \
  --profile safe-web-baseline \
  --runtime container
```

Notes:

- `--runtime container` makes the toolkit-runner invoke scanner containers
  via the host Docker socket if it is mounted, or fall back to the
  in-runner host backend if not
- raw artifacts, normalized findings, and the executive summary are written
  to `/workspace/outputs/<run-id>/...` and persist to `./outputs` on the host
- the runner reads the YAML bundle from `/workspace/config`

Required environment variables (set via `compose/toolkit-runner.env`):

- `SAMPLE_API_BEARER_TOKEN` — only needed when running the sample-api pack
- `NUCLEI_DISABLE_UPDATE_CHECK=true` — recommended for deterministic runs

## Live Chaos Through Compose

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

Run the chaos workflow:

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
summary from any earlier run:

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

## See Also

- `docs/explanation/compose-workflow-model.md` — service topology rationale
- `docs/explanation/container-runtime-model.md` — Docker runtime backend
- `docs/reference/cli.md` — command reference
