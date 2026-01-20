import os
import radon.complexity as cc
from radon.metrics import mi_visit
from radon.raw import analyze
from typing import Dict, Any

def analyze_quality(repo_path: str) -> Dict[str, Any]:
    """
    Scans Python files in the repo to calculate:
    1. Cyclomatic Complexity (Logic difficulty)
    2. Maintainability Index (Code health)
    3. Docstring coverage (Documentation)
    """
    # Validate repo_path
    if not repo_path or not os.path.exists(repo_path):
        print(f"⚠️ Quality check skipped: invalid repo_path ({repo_path})")
        return {
            "avg_complexity": 5,
            "maintainability_index": 60,
            "documentation_score": 40,
            "analyzed_files": 0
        }
    
    total_complexity = 0
    total_maintainability = 0
    total_loc = 0
    total_comments = 0
    py_files_count = 0

    for root, _, files in os.walk(repo_path):
        for f in files:
            if f.endswith(".py"):
                full_path = os.path.join(root, f)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as file:
                        content = file.read()
                        if not content.strip():
                            continue

                        # 1. Complexity
                        blocks = cc.cc_visit(content)
                        if blocks:
                            file_complexity = sum(b.complexity for b in blocks) / len(blocks)
                        else:
                            file_complexity = 1 # Base complexity
                        
                        # 2. Maintainability (0-100)
                        # A score < 50 is bad. > 75 is good.
                        maintainability = mi_visit(content, multi=True)

                        # 3. Raw stats (Comments vs Code)
                        raw_stats = analyze(content)
                        
                        total_complexity += file_complexity
                        total_maintainability += maintainability
                        total_loc += raw_stats.loc
                        total_comments += raw_stats.comments
                        py_files_count += 1

                except Exception:
                    continue

    # Averages
    if py_files_count > 0:
        avg_cc = total_complexity / py_files_count
        avg_mi = total_maintainability / py_files_count
    else:
        # No Python files found - use neutral scores (not 0)
        # This prevents penalizing JS/TS/Go projects
        avg_cc = 5  # Average complexity
        avg_mi = 60  # Neutral maintainability

    # Documentation Score calculation (Comment to Code ratio)
    # Ideal ratio is roughly 1:5 or 20%
    if total_loc > 0:
        doc_ratio = total_comments / total_loc
        # Normalize: if > 15%, give 100 points, else scale it
        doc_score = min(1.0, doc_ratio / 0.15) * 100
    else:
        doc_score = 40  # Neutral score for non-Python projects

    return {
        "avg_complexity": round(avg_cc, 2),         # Lower is better (ideally < 10)
        "maintainability_index": round(avg_mi, 2),  # Higher is better (ideally > 75)
        "documentation_score": round(doc_score, 2), # Higher is better (0-100)
        "analyzed_files": py_files_count
    }