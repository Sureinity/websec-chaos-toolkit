"""Markdown report scaffolding."""

from collections import defaultdict
from pathlib import Path

from toolkit.results.io import read_normalized_results_from_path
from toolkit.results.models import NormalizedResult

REPORTS_DIR_NAME = "reports"
EXECUTIVE_SUMMARY_FILE_NAME = "executive-summary.md"
NORMALIZED_DIR_NAME = "normalized"
FINDINGS_FILE_NAME = "findings.json"


_SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def default_run_output_dir(base_dir: Path, run_id: str) -> Path:
    """Return the stable output directory for a run id."""

    return base_dir / run_id


def executive_summary_path(run_dir: Path) -> Path:
    """Return the canonical Markdown summary path for a run."""

    return run_dir / REPORTS_DIR_NAME / EXECUTIVE_SUMMARY_FILE_NAME


def normalized_results_bundle_path(run_dir: Path) -> Path:
    """Return the canonical normalized results bundle path for a run."""

    return run_dir / NORMALIZED_DIR_NAME / FINDINGS_FILE_NAME


def build_markdown_summary(run_id: str, results: list[NormalizedResult]) -> str:
    """Build a simple markdown summary from normalized results."""

    lines = [
        f"# Run Summary: {run_id}",
        "",
        f"Total findings: {len(results)}",
        "",
    ]

    if not results:
        lines.append("No findings were normalized for this run.")
        return "\n".join(lines)

    grouped_results: dict[str, dict[str, list[NormalizedResult]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for result in sorted(results, key=_result_sort_key):
        grouped_results[result.app_id][result.severity].append(result)

    for app_id in sorted(grouped_results):
        lines.extend(
            [
                f"## {app_id}",
                "",
            ]
        )
        severities = sorted(grouped_results[app_id], key=lambda severity: _SEVERITY_ORDER[severity])
        for severity in severities:
            severity_results = grouped_results[app_id][severity]
            lines.extend(
                [
                    f"### {severity} ({len(severity_results)})",
                    "",
                ]
            )
            for result in severity_results:
                lines.extend(
                    [
                        f"- Environment: {result.environment}",
                        f"- Target: {result.target}",
                        f"- Tool: {result.tool}",
                        f"- Category: {result.category}",
                        f"- Confidence: {result.confidence}",
                        f"- Remediation: {result.remediation_summary}",
                        "",
                    ]
                )

    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def build_markdown_summary_from_run_dir(run_dir: Path) -> str:
    """Load normalized results from disk and render the Markdown summary."""

    results = read_normalized_results_from_path(normalized_results_bundle_path(run_dir))
    return build_markdown_summary(run_id=run_dir.name, results=results)


def write_markdown_summary(run_dir: Path) -> Path:
    """Render and write the canonical Markdown summary for a run directory."""

    summary_path = executive_summary_path(run_dir)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(build_markdown_summary_from_run_dir(run_dir) + "\n", encoding="utf-8")
    return summary_path


def _result_sort_key(result: NormalizedResult) -> tuple[str, int, str, str, str]:
    return (
        result.app_id,
        _SEVERITY_ORDER[result.severity],
        result.target,
        result.tool,
        result.category,
    )
