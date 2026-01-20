import os
from src.utils.file_utils import read_file

def generate_repo_summary(repo_path: str, max_chars: int = 40000) -> str:
    """
    Compresses the repository into a text summary for the LLM.
    """
    # Validate repo_path
    if not repo_path or not os.path.exists(repo_path):
        return f"Repository summary unavailable: invalid path ({repo_path})"
    
    summary = []
    
    # 1. Directory Tree
    summary.append("=== DIRECTORY STRUCTURE ===")
    for root, _, files in os.walk(repo_path):
        level = root.replace(repo_path, '').count(os.sep)
        indent = ' ' * 2 * level
        summary.append(f"{indent}{os.path.basename(root)}/")
        for f in files:
            if not f.startswith(".") and not f.endswith((".pyc", ".lock", ".png", ".jpg")):
                summary.append(f"{indent}  {f}")
    
    # 2. Key Config Files (Full Read)
    summary.append("\n=== CRITICAL CONFIGURATION ===")
    critical = ["README.md", "requirements.txt", "package.json", "Dockerfile", "schema.sql", ".env.example"]
    for fname in critical:
        p = os.path.join(repo_path, fname)
        if os.path.exists(p):
            content = read_file(p)
            summary.append(f"\n--- {fname} ---\n{content[:2000]}")

    # 3. Source Code Sampling (Top 10 Files)
    summary.append("\n=== SOURCE CODE SAMPLES ===")
    code_files = []
    for root, _, files in os.walk(repo_path):
        for f in files:
            if f.endswith((".py", ".js", ".java", ".go", ".ts", ".cpp")):
                code_files.append(os.path.join(root, f))
    
    # Sort by size (largest files often have the main logic)
    top_files = sorted(code_files, key=os.path.getsize, reverse=True)[:10]
    
    current_chars = 0
    for fpath in top_files:
        if current_chars > max_chars: break
        rel = fpath.replace(repo_path, "")
        content = read_file(fpath)
        snippet = content[:3000] # Limit per file
        summary.append(f"\n--- FILE: {rel} ---\n{snippet}\n")
        current_chars += len(snippet)

    return "\n".join(summary)