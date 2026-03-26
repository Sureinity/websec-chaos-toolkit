"""Markdown report scaffolding."""

from pathlib import Path

from toolkit.results.models import NormalizedResult


def default_run_output_dir(base_dir: Path, run_id: str) -> Path:
    """Return the stable output directory for a run id."""

    return base_dir / run_id


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

    for result in results:
        lines.extend(
            [
                f"## {result.app_id} [{result.severity}]",
                f"- Environment: {result.environment}",
                f"- Target: {result.target}",
                f"- Tool: {result.tool}",
                f"- Category: {result.category}",
                f"- Confidence: {result.confidence}",
                f"- Remediation: {result.remediation_summary}",
                "",
            ]
        )

    return "\n".join(lines)
