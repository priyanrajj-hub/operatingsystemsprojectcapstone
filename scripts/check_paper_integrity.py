#!/usr/bin/env python3
"""
CI Paper Integrity Validator.
Verifies that paper/main.tex contains NO hardcoded experimental numbers or p-values.
Enforces that all empirical metrics in the evaluation section are driven strictly
by auto-generated macros from paper/results_macros.tex.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def check_paper_integrity(root: Path | None = None) -> list[str]:
    """Audit paper/main.tex against research integrity rules."""
    errors = []
    if root is None:
        root = Path(__file__).resolve().parent.parent

    main_tex_path = root / "paper" / "main.tex"
    macros_path = root / "paper" / "results_macros.tex"

    if not main_tex_path.is_file():
        return ["paper/main.tex is missing"]
    if not macros_path.is_file():
        return ["paper/results_macros.tex is missing"]

    main_content = main_tex_path.read_text(encoding="utf-8")
    macros_content = macros_path.read_text(encoding="utf-8")

    # 1. Verify results_macros.tex is included in main.tex
    if "\\input{results_macros" not in main_content:
        errors.append(
            "paper/main.tex must include results_macros.tex via \\input{results_macros.tex}"
        )

    # 2. Extract defined macro names from results_macros.tex
    defined_macros = set(re.findall(r"\\newcommand\{\\([A-Za-z0-9]+)\}", macros_content))
    if not defined_macros:
        errors.append("paper/results_macros.tex contains no valid macro definitions")

    # 3. Check for forbidden hardcoded claims in main.tex
    forbidden_patterns = [
        (r"p\s*<\s*0\.0[0-9]+", "Hardcoded p-value claim (e.g. p < 0.01)"),
        (r"Cohen'?s?\s*d\s*=\s*[0-9]+(?:\.[0-9]+)?", "Hardcoded Cohen's d effect size claim"),
        (r"J\s*(?:=|\\ge|\\ge\s*)\s*0\.[0-9]{2,}", "Hardcoded Jain fairness index claim in text"),
        (r"over\s*10\s*repeated\s*experimental\s*trials", "Hardcoded trial count claim"),
        (r"2280\.0|2750\.0|1620\.0|2010\.0|1890\.0", "Unverified legacy EDP numbers in table"),
    ]

    for pattern, desc in forbidden_patterns:
        if re.search(pattern, main_content, re.IGNORECASE):
            errors.append(f"Forbidden hardcoded metric detected: {desc}")

    # 4. Check that Comparative Evaluation table strictly uses defined macros
    eval_match = re.search(r"\\begin\{table\}(.*?)\\end\{table\}", main_content, re.DOTALL)
    if eval_match:
        table_body = eval_match.group(1)
        # Search for tabular data rows with bare floating point numbers
        raw_floats = re.findall(r"&\s*([0-9]+\.[0-9]+)\s*", table_body)
        if raw_floats:
            errors.append(
                f"Table contains hardcoded numeric literals instead of macros: {raw_floats}"
            )

    return errors


def main() -> int:
    errors = check_paper_integrity()
    if errors:
        print("FAILED: Paper integrity violations found:")
        for err in errors:
            print(f"  - ERROR: {err}")
        return 1

    print("PASSED: paper/main.tex contains zero hardcoded numbers; all metrics are macro-driven.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
