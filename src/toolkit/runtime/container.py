"""Docker-backed container runtime for scanner tool execution.

Translates adapter execution intent into docker run invocations with
bind mounts for raw output. The container runs with --network=host so the
target app remains reachable. Config inputs and output directories are
mounted read-write; no other host paths are exposed.

Failure contract:
- Missing Docker binary on PATH: AdapterAvailability(available=False).
- Missing container image: RuntimeResult with non-zero returncode.
- Container execution failure: RuntimeResult with non-zero returncode.
"""

from pathlib import Path

from toolkit.adapters.base import AdapterAvailability
from toolkit.adapters.process import find_binary, run_process_command
from toolkit.core.logging import ProcessLogContext
from toolkit.runtime.contracts import CONTAINER_TOOL_ALIASES, CONTAINER_TOOL_IMAGES
from toolkit.runtime.models import RuntimeRequest, RuntimeResult


class ContainerRuntime:
    """Execute scanner tools inside Docker containers."""

    def __init__(
        self,
        *,
        image_overrides: dict[str, str] | None = None,
    ) -> None:
        self._image_overrides = dict(image_overrides or {})

    def check_tool_available(self, tool: str) -> AdapterAvailability:
        docker_path = find_binary("docker")
        if docker_path is None:
            return AdapterAvailability(
                available=False,
                reason="docker binary was not found on PATH",
                binary="docker",
            )
        image = self._resolve_image(tool)
        if image is None:
            return AdapterAvailability(
                available=False,
                reason=f"no container image configured for tool: {tool}",
                binary="docker",
            )
        return AdapterAvailability(
            available=True,
            binary=f"docker:{image}",
        )

    def execute(self, request: RuntimeRequest) -> RuntimeResult:
        image = self._resolve_image(request.tool)
        if image is None:
            return RuntimeResult(
                command=request.command,
                returncode=1,
                stdout="",
                stderr=(f"no container image configured for tool: {request.tool}"),
            )

        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        docker_command = self._build_docker_command(request, image=image)
        completed = run_process_command(
            command=docker_command,
            env_overrides=request.env_overrides,
            timeout_seconds=request.timeout_seconds,
            stream_output=True,
            log_context=ProcessLogContext(
                runtime="container",
                tool=request.tool,
                output_path=request.output_path,
                cwd=request.cwd,
            ),
        )

        return RuntimeResult(
            command=completed.command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=completed.timed_out,
        )

    def _resolve_image(self, tool: str) -> str | None:
        tool = CONTAINER_TOOL_ALIASES.get(tool, tool)
        if tool in self._image_overrides:
            return self._image_overrides[tool]
        return CONTAINER_TOOL_IMAGES.get(tool)

    def _build_docker_command(
        self,
        request: RuntimeRequest,
        *,
        image: str,
    ) -> tuple[str, ...]:
        container_output_dir = _container_output_dir(request)
        parts: list[str] = [
            "docker",
            "run",
            "--rm",
            "--network=host",
        ]

        # Mount the output directory so the tool can write artifacts.
        # The :z suffix relabels the mount for SELinux-enabled hosts
        # (Fedora, RHEL, CentOS) so the container user can write.
        output_dir = request.output_path.parent
        parts.extend(
            [
                "-v",
                f"{output_dir}:{container_output_dir}:z",
            ]
        )

        # Mount cwd when specified. If it differs from the output dir it needs
        # a dedicated mount; if it matches, the output-dir mount already covers
        # it but we still set -w so relative file arguments resolve correctly.
        if request.cwd is not None:
            if request.cwd != output_dir:
                parts.extend(["-v", f"{request.cwd}:{request.cwd}:z"])
            parts.extend(["-w", str(request.cwd)])

        # Forward env overrides as container env vars.
        for key, value in request.env_overrides.items():
            parts.extend(["-e", f"{key}={value}"])

        # Override the entrypoint with the actual tool binary so the
        # command works regardless of whether the image defines one.
        if request.command:
            parts.extend(["--entrypoint", request.command[0]])

        parts.append(image)

        # Append the remaining command arguments after the image.
        if len(request.command) > 1:
            parts.extend(
                _translated_tool_args(
                    request,
                    container_output_dir=container_output_dir,
                )
            )

        return tuple(parts)


def _container_output_dir(request: RuntimeRequest) -> Path:
    if request.tool == "zap":
        # The ZAP baseline image expects file outputs to live under /zap/wrk.
        return Path("/zap/wrk")
    return request.output_path.parent


def _translated_tool_args(
    request: RuntimeRequest,
    *,
    container_output_dir: Path,
) -> tuple[str, ...]:
    translated_args: list[str] = []
    if request.tool == "zap":
        # The ZAP baseline wrapper already assumes /zap/wrk as reportDir inside
        # the container, so its -J argument must be the report filename only.
        container_output_arg = request.output_path.name
    else:
        container_output_arg = str(container_output_dir / request.output_path.name)

    for arg in request.command[1:]:
        if arg == str(request.output_path):
            translated_args.append(container_output_arg)
            continue
        translated_args.append(arg)

    return tuple(translated_args)
