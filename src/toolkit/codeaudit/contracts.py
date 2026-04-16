"""Locked contract for the planned URL-first code audit workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from toolkit.pentest.contracts import PentestAssessmentMode, tool_supported_in_mode

CodeAuditToolName = Literal["semgrep", "trivy"]

CODE_AUDIT_DEFAULT_TOOLS: tuple[CodeAuditToolName, ...] = ("semgrep", "trivy")
CODE_AUDIT_ALLOWED_TOOLS: frozenset[CodeAuditToolName] = frozenset(CODE_AUDIT_DEFAULT_TOOLS)
CODE_AUDIT_EXCLUDED_TOOLS: frozenset[str] = frozenset({"zap", "nuclei", "nmap"})


@dataclass(slots=True, frozen=True)
class CodeAuditContract:
    """Decision-complete contract for the simple code-audit operator path."""

    assessment_mode: PentestAssessmentMode
    target_kind: str
    requires_yaml_config: bool
    supports_multiple_paths: bool
    supports_image_targets: bool
    default_tools: tuple[CodeAuditToolName, ...]
    allowed_tools: frozenset[CodeAuditToolName]
    excluded_tools: frozenset[str]


CODE_AUDIT_CONTRACT = CodeAuditContract(
    assessment_mode=PentestAssessmentMode.SOURCE_TREE,
    target_kind="source_tree_path",
    requires_yaml_config=False,
    supports_multiple_paths=False,
    supports_image_targets=False,
    default_tools=CODE_AUDIT_DEFAULT_TOOLS,
    allowed_tools=CODE_AUDIT_ALLOWED_TOOLS,
    excluded_tools=CODE_AUDIT_EXCLUDED_TOOLS,
)


def code_audit_supports_tool(tool: str) -> bool:
    """Return whether a tool is part of the planned code-audit surface."""

    return tool in CODE_AUDIT_CONTRACT.allowed_tools


def code_audit_contract_matches_pentest_modes() -> bool:
    """Return whether the planned code-audit toolset matches source_tree mode."""

    return all(
        tool_supported_in_mode(tool, CODE_AUDIT_CONTRACT.assessment_mode)
        for tool in CODE_AUDIT_CONTRACT.default_tools
    ) and all(
        not tool_supported_in_mode(tool, CODE_AUDIT_CONTRACT.assessment_mode)
        for tool in CODE_AUDIT_CONTRACT.excluded_tools
    )
