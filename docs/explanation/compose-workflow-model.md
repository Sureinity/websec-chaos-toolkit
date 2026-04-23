# Compose Workflow Model

This document explains the service topology defined by the checked-in Docker
Compose assets, why that topology is the preferred portability model, and how
Compose service names map to `apps.yaml` configuration.

## Why Compose

Direct CLI use is fast for development, but it puts the burden of installing
scanner binaries, Toxiproxy, and the target app on the operator. The checked-in
Compose assets make that environment declarative and portable as a topology
baseline across CI, staging boxes, and operator workstations.

The Compose path is preferred because:

- one `docker compose up` brings the runner, target, and Toxiproxy
  online together
- service-name DNS makes target reachability deterministic
- no scanner binaries or Toxiproxy installs are required on the host
- the same setup works on any Linux host with Docker Compose installed

Current repository coverage for this path is static-contract only:

- `tests/integration/test_compose_workflow.py` verifies file presence, service
  definitions, mounts, network wiring, and config-pack alignment
- the checked-in `toolkit-runner` service is still a placeholder container, not
  a prebuilt toolkit image

## Service Topology

A complete Compose environment defines three services on a shared
bridge network (`toolkit-net`):

```
   +---------------------+
   |   toolkit-runner    |
   |   (toolkit CLI)     |
   +----------+----------+
              |
              |  service-name DNS
              |
   +----------v----------+        +---------------+
   |     sample-app      |<------>|   toxiproxy   |
   |   (target app)      |        |  (admin API,  |
   +---------------------+        |   chaos only) |
                                  +---------------+

   shared network: toolkit-net
```

| Service | Role | Required for |
|---------|------|--------------|
| `toolkit-runner` | placeholder runner workspace | every workflow |
| `sample-app` | the target application | every workflow |
| `toxiproxy` | admin API for fault injection | chaos workflows only |

The Toxiproxy service is gated behind the `chaos` Compose profile so
pentest-only operators do not pull it unnecessarily.

## Service Name to apps.yaml Mapping

On the `toolkit-net` network, services resolve each other by service
name. The example `sample-webapp-compose` config pack uses these
mappings:

| Compose service | apps.yaml field | Value |
|----|----|----|
| `sample-app` | `base_url` | `http://sample-app:8080` |
| `sample-app` | `host_targets[0]` | `sample-app` |
| `sample-app` | `target_allowlist[0]` | `sample-app` |
| `toxiproxy` | (toolkit env) | `TOOLKIT_TOXIPROXY_URL=http://toxiproxy:8474` |

The `target_service` in chaos profiles refers to the **Toxiproxy proxy
name**, which by convention matches the Compose service name being
fronted (so `target_service: sample-app` proxies the `sample-app`
service).

## Operator Modes

### Pentest only

```bash
docker compose up -d toolkit-runner sample-app
```

Brings up the runner and target. Toxiproxy is not started. The
checked-in assets guarantee mounts and networking for the runner workspace.

### Pentest + chaos

```bash
docker compose --profile chaos up -d toolkit-runner sample-app toxiproxy
```

Adds the Toxiproxy service. The toolkit container can additionally
expose the Toxiproxy admin API at `http://toxiproxy:8474` on the shared
network.

### Host-independent

The same `docker-compose.yml` defines the topology on any Linux host that has
Docker Compose v2 installed. No scanner binaries are required on the host to
bring up the checked-in services.

## Mounted Volumes

The runner expects a stable mount layout:

| Host path | Container path | Mode |
|-----------|---------------|------|
| `examples/configs/sample-webapp` | `/workspace/config` | read-only |
| `outputs/` | `/workspace/outputs` | read-write |
| `src/` | `/workspace/src` | read-only |
| `pyproject.toml` | `/workspace/pyproject.toml` | read-only |
| `uv.lock` | `/workspace/uv.lock` | read-only |

Run artifacts written to `/workspace/outputs` persist back to the
host so operators can inspect them, attach them to tickets, or feed
them into report rebuild commands later.

## Falling Back To Direct CLI

Compose is the preferred path but not the only one. The same
toolkit commands run via `uv run toolkit ...` directly on the host
when Compose is not available, with `--runtime host` (default) or
`--runtime container` selecting the execution backend.

## What This Model Does Not Cover

- Production deployment of the toolkit (the toolkit is a security
  testing tool, not a production runtime)
- Kubernetes orchestration (planned later if needed)
- Authenticated container registries beyond the public defaults
- Multi-host Compose setups (the toolkit runs on one host at a time)

## See Also

- `docs/how-to/run-with-compose.md` — operator task guide
- `docs/explanation/container-runtime-model.md` — container runtime backend
- `compose/examples/sample-webapp-compose/` — example overlay
- `examples/configs/sample-webapp-compose/` — Compose-aware config pack
