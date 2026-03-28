"""Read and write normalized result bundles for a run."""

import json
from pathlib import Path

from toolkit.core.run_context import RunContext
from toolkit.results.models import NormalizedResult

NORMALIZED_RESULTS_FILE_NAME = "findings.json"


def normalized_results_path(context: RunContext) -> Path:
    """Return the canonical normalized bundle path for a run."""

    return context.normalized_dir / NORMALIZED_RESULTS_FILE_NAME


def write_normalized_results(
    context: RunContext,
    results: list[NormalizedResult],
) -> Path:
    """Write normalized results using stable JSON formatting."""

    payload = [result.model_dump(mode="json") for result in results]
    path = normalized_results_path(context)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def read_normalized_results(context: RunContext) -> list[NormalizedResult]:
    """Load normalized results from the canonical bundle path."""

    return read_normalized_results_from_path(normalized_results_path(context))


def read_normalized_results_from_path(path: Path) -> list[NormalizedResult]:
    """Load normalized results from an explicit path."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return [NormalizedResult.model_validate(item) for item in payload]
