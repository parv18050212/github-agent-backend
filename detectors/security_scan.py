import re
import os
from typing import Dict, Any, List

# Patterns for common high-risk secrets
PATTERNS = {
    "AWS Access Key": r"(?<![A-Z0-9])[A-Z0-9]{20}(?![A-Z0-9])",  # Basic heuristic
    "AWS Secret": r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])",
    "Google API Key": r"AIza[0-9A-Za-z\\-_]{35}",
    "Generic Private Key": r"-----BEGIN PRIVATE KEY-----",
    "OpenAI API Key": r"sk-[a-zA-Z0-9]{48}",
    "Hardcoded Password": r"(password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{3,}['\"]",
    "DB Connection String": r"mysql://|postgresql://|mongodb://"
}

def scan_for_secrets(repo_path: str) -> Dict[str, Any]:
    leaks = []
    
    # Walk through files
    for root, _, files in os.walk(repo_path):
        for f in files:
            # Skip hidden files, images, and lock files
            if f.startswith(".") or f.endswith((".png", ".jpg", ".lock", ".pyc")):
                continue
            
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as file_in:
                    lines = file_in.readlines()
                    
                for i, line in enumerate(lines):
                    for name, pattern in PATTERNS.items():
                        if re.search(pattern, line):
                            # Record minute detail: File, Line #, Type
                            leaks.append({
                                "file": f,
                                "path": path.replace(repo_path, ""), # Relative path
                                "line_number": i + 1,
                                "type": name,
                                "snippet": line.strip()[:50] + "..." # Truncated for display
                            })
            except Exception:
                continue
                
    # Calculate Score (100 = Safe, -20 per leak)
    security_penalty = min(100, len(leaks) * 20)
    
    return {
        "score": 100 - security_penalty,
        "leak_count": len(leaks),
        "details": leaks
    }