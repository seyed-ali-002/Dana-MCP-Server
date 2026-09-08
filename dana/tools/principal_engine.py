from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .engineering import _manifest, _python_inventory, _reuse, _root


def register_principal_engine_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def dana_architecture_review(path: str = ".", goal: str = "") -> dict[str, Any]:
        """Kun-inspired principal engineering review of architecture and implementation options."""
        root = _root(path)
        inventory = _python_inventory(root)
        manifests = _manifest(root)
        return {
            "goal": goal,
            "root": str(root),
            "manifests": manifests,
            "definition_count": len(inventory["definitions"]),
            "key_definitions": inventory["definitions"][:150],
            "existing_matches": _reuse(root, goal, 20),
            "review": {
                "constraints": [
                    "preserve existing public behavior",
                    "prefer incremental changes",
                    "avoid unnecessary dependencies",
                ],
                "decision_framework": [
                    "problem",
                    "constraints",
                    "existing architecture",
                    "options",
                    "tradeoffs",
                    "smallest reversible step",
                    "validation",
                ],
                "recommended_next_step": "inspect existing matches before creating new abstractions",
            },
        }

    @mcp.tool()
    def dana_engineering_decision(
        problem: str, options: list[str], constraints: list[str] | None = None
    ) -> dict[str, Any]:
        """Produce a transparent tradeoff matrix for engineering decisions."""
        if not options:
            raise ValueError("At least one option is required")
        constraints = constraints or []
        scored = []
        for index, option in enumerate(options, 1):
            text = option.lower()
            risk = sum(
                word in text
                for word in ("rewrite", "new dependency", "migration", "distributed")
            )
            complexity = len(option.split())
            scored.append(
                {
                    "option": option,
                    "risk": risk,
                    "complexity_hint": complexity,
                    "rank": index,
                }
            )
        ranked = sorted(
            scored, key=lambda item: (item["risk"], item["complexity_hint"])
        )
        return {
            "problem": problem,
            "constraints": constraints,
            "options": scored,
            "recommended": ranked[0]["option"],
            "principle": "prefer the smallest reversible option that satisfies the constraints",
            "validation": [
                "tests",
                "lint/type checks",
                "runtime verification",
                "rollback plan",
            ],
        }

    @mcp.tool()
    def dana_create_implementation_plan(goal: str, path: str = ".") -> dict[str, Any]:
        """Create an execution plan grounded in the existing codebase."""
        root = _root(path)
        matches = _reuse(root, goal, 15)
        steps = [
            "Clarify observable acceptance criteria",
            "Inspect existing matches and reuse opportunities",
            "Choose smallest safe design",
            "Implement isolated change",
            "Run targeted tests",
            "Run broader validation",
            "Review diff and rollback impact",
        ]
        return {
            "goal": goal,
            "root": str(root),
            "existing_context": matches,
            "steps": steps,
            "done_definition": [
                "behavior works",
                "no unrelated regressions",
                "tests pass",
                "change is explainable and reversible",
            ],
        }
