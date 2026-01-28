import argparse
import os
import sys
import csv
import json
import time
from datetime import datetime
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()

# --- CONFIGURATION ---
INPUT_FILE = "D://HackEval Final//proj-github//team details .xlsx" 

# --- Import Core Utils ---
from src.orchestrator.langgraph_adapter import SimpleLangGraph
from src.utils.git_utils import clone_repo, cleanup_repo, list_files
from src.utils.file_utils import read_file, generate_tree_structure

# --- Import Detectors ---
from src.detectors.commit_forensics import analyze_commits
from src.detectors.llm_detector import llm_origin_ensemble
from src.detectors.quality_metrics import analyze_quality
from src.detectors.alg_detector import algorithmic_similarity 
from src.detectors.security_scan import scan_for_secrets
from src.detectors.stack_detector import detect_tech_stack
from src.detectors.product_evaluator import evaluate_product_logic
from src.detectors.maturity_scanner import scan_project_maturity
from src.detectors.structure_analyzer import analyze_structure
from src.utils.visualizer import generate_dashboard

# ==========================================
# 1. Pipeline Nodes
# ==========================================

def node_clone_repo(ctx):
    url = ctx.get("repo_url")
    progress_callback = ctx.get("progress_callback")
    
    if progress_callback:
        progress_callback("cloning", 10)
    
    print(f"\n[1/10] 📥 Cloning repository...")
    try:
        repo_path = clone_repo(url, depth=None)
        return {"repo_path": repo_path}
    except Exception as e:
        print(f"      ❌ Clone failed: {e}")
        raise

def node_stack_id(ctx):
    progress_callback = ctx.get("progress_callback")
    
    if progress_callback:
        progress_callback("stack_detection", 20)
    
    print(f"[2/10] 🔎 Identifying Tech Stack...")
    return {"tech_stack": detect_tech_stack(ctx.get("repo_path"))}

def node_structure_analysis(ctx):
    progress_callback = ctx.get("progress_callback")
    
    if progress_callback:
        progress_callback("structure_analysis", 30)
    
    print(f"[3/10] 🏗️  Analyzing Architecture & Organization...")
    return {"structure": analyze_structure(ctx.get("repo_path"))}

def node_maturity_check(ctx):
    progress_callback = ctx.get("progress_callback")
    
    if progress_callback:
        progress_callback("maturity_check", 40)
    
    print(f"[4/10] 🚀 Checking Deployment & Testing Maturity...")
    return {"maturity": scan_project_maturity(ctx.get("repo_path"))}

def node_commit_forensics(ctx):
    progress_callback = ctx.get("progress_callback")
    
    if progress_callback:
        progress_callback("commit_forensics", 50)
    
    print(f"[5/10] 🕵️  Analyzing Team Effort & Git History...")
    return {"commit_analysis": analyze_commits(ctx.get("repo_path"))}

def node_quality_check(ctx):
    progress_callback = ctx.get("progress_callback")
    
    if progress_callback:
        progress_callback("quality_check", 60)
    
    print(f"[6/10] ⚖️  Assessing Code Quality & Documentation...")
    return {"quality_metrics": analyze_quality(ctx.get("repo_path"))}

def node_security_check(ctx):
    progress_callback = ctx.get("progress_callback")
    
    if progress_callback:
        progress_callback("security_scan", 70)
    
    print(f"[7/10] 🔐 Scanning for API Leaks & Secrets...")
    return {"security_report": scan_for_secrets(ctx.get("repo_path"))}

def node_forensic_analysis(ctx):
    progress_callback = ctx.get("progress_callback")
    
    if progress_callback:
        progress_callback("forensic_analysis", 80)
    
    print(f"[8/10] 🤖 Running Deep Forensics (AI & Plagiarism)...")
    repo_path = ctx.get("repo_path")
    providers = ctx.get("llm_providers", [])
    
    files = list_files(repo_path, ext_whitelist=[
        ".py", ".js", ".java", ".cpp", ".ts", ".go",
        ".jsx", ".tsx", ".c", ".h", ".cs", ".rs", ".php", 
        ".rb", ".swift", ".kt", ".scala", ".dart"
    ])
    
    file_contents = {}
    for f in files:
        content = read_file(f)
        if len(content) > 100: 
            file_contents[f] = {"content": content, "tokens": content.split()}

    # LLM Detection (Top 15 files)
    llm_results = {}
    target_files = sorted(file_contents.keys(), key=lambda k: len(file_contents[k]["content"]), reverse=True)[:15]
    for f in target_files:
        doc = file_contents[f]
        res = llm_origin_ensemble(doc, providers=providers)
        llm_results[f] = res["score"]

    # Internal Plagiarism (Top 20 files)
    plag_results = {}
    pool = sorted(file_contents.keys(), key=lambda k: len(file_contents[k]["content"]), reverse=True)[:20]
    for f_a in pool:
        best_score = 0.0
        best_file = None
        for f_b in pool:
            if f_a == f_b: continue
            sim = algorithmic_similarity(file_contents[f_a], file_contents[f_b])
            if sim["score"] > best_score:
                best_score = sim["score"]
                best_file = f_b
        plag_results[f_a] = {"score": best_score, "match": best_file}

    return {"llm_data": llm_results, "plag_data": plag_results}

def node_ai_judge(ctx):
    progress_callback = ctx.get("progress_callback")
    
    if progress_callback:
        progress_callback("ai_judge", 90)
    
    print(f"[9/10] 🧠 Gemini (2.5) is reviewing the product logic...")
    api_key = ctx.get("gemini_key") or os.environ.get("GEMINI_API_KEY")
    return {"ai_judgment": evaluate_product_logic(ctx.get("repo_path"), api_key)}

def node_aggregator(ctx):
    progress_callback = ctx.get("progress_callback")
    
    if progress_callback:
        progress_callback("aggregation", 95)
    
    print(f"[10/10] 📊 Generating Final Evaluation Report...")
    
    # Inputs with type validation
    repo_path = ctx.get("repo_path")
    
    # Ensure all inputs are dicts (not lists or None)
    qual = ctx.get("quality_metrics") or {}
    if not isinstance(qual, dict):
        print(f"⚠️ Warning: quality_metrics is {type(qual)}, using empty dict")
        qual = {}
    
    comm = ctx.get("commit_analysis") or {}
    if not isinstance(comm, dict):
        print(f"⚠️ Warning: commit_analysis is {type(comm)}, using empty dict")
        comm = {}
    
    sec = ctx.get("security_report") or {}
    if not isinstance(sec, dict):
        print(f"⚠️ Warning: security_report is {type(sec)}, using empty dict")
        sec = {}
    
    llm = ctx.get("llm_data") or {}
    if not isinstance(llm, dict):
        print(f"⚠️ Warning: llm_data is {type(llm)}, using empty dict")
        llm = {}
    
    plag = ctx.get("plag_data") or {}
    if not isinstance(plag, dict):
        print(f"⚠️ Warning: plag_data is {type(plag)}, using empty dict")
        plag = {}
    
    stack = ctx.get("tech_stack") or []
    if not isinstance(stack, list):
        print(f"⚠️ Warning: tech_stack is {type(stack)}, using empty list")
        stack = []
    
    judge = ctx.get("ai_judgment") or {}
    if not isinstance(judge, dict):
        print(f"⚠️ Warning: ai_judgment is {type(judge)}, using empty dict")
        judge = {}
    
    mat = ctx.get("maturity") or {}
    if not isinstance(mat, dict):
        print(f"⚠️ Warning: maturity is {type(mat)}, using empty dict")
        mat = {}
    
    struct = ctx.get("structure") or {}
    if not isinstance(struct, dict):
        print(f"⚠️ Warning: structure is {type(struct)}, using empty dict")
        struct = {}
    
    # --- Generate Tree (For Output) ---
    repo_tree = "Tree generation skipped (missing repo_path)" 
    if repo_path and os.path.exists(repo_path):
        try:
            repo_tree = generate_tree_structure(repo_path)
        except Exception as e:
            print(f"⚠️ Tree generation failed: {e}")
            repo_tree = f"Tree generation failed: {str(e)}"

    # --- Process Files ---
    detailed_files = []
    viz_files = []
    all_files = set(llm.keys()) | set(plag.keys())
    
    for fpath in all_files:
        s_ai = llm.get(fpath, 0.0)
        s_plag = plag.get(fpath, {}).get("score", 0.0)
        risk = ((s_ai * 0.6) + (s_plag * 0.4)) * 100
        
        viz_files.append({"path": fpath, "S_llm": s_ai, "S_alg": s_plag, "S_cross": max(s_ai, s_plag)})
        
        if risk > 15: 
            match_path = plag.get(fpath, {}).get("match", "") or ""
            detailed_files.append({
                "name": os.path.basename(fpath),
                "ai_pct": s_ai * 100,
                "plag_pct": s_plag * 100,
                "risk": risk,
                "match": os.path.basename(match_path) if match_path else "None"
            })
            
    detailed_files.sort(key=lambda x: x['risk'], reverse=True)
    
    # Calculate overall AI percentage from all files (not just risky ones)
    all_ai_scores = [llm.get(f, 0.0) * 100 for f in llm.keys()]
    overall_ai_percentage = round(sum(all_ai_scores) / len(all_ai_scores), 2) if all_ai_scores else 0.0
    top_ai = max(all_ai_scores) if all_ai_scores else 0.0
    
    # --- Scores ---
    # Use reasonable defaults (50 = neutral) instead of 0 when data is missing
    impl_score = judge.get("implementation_score", 50)  # 50 is neutral if AI fails
    
    # Calculate Effort based on Relevance Score (capped at 100)
    # Target: 50 relevance points = 100 score (approx 20 meaningful commits)
    relevance = comm.get("total_relevance", 0)
    effort_score = min(100, relevance * 2) 
    
    scores = {
        "originality": max(0, 100 - top_ai),
        "quality": qual.get("maintainability_index", 50),  # 50 if no Python files
        "security": sec.get("score", 100),  # 100 if no scan done (assume safe)
        "effort": effort_score,
        "implementation": impl_score,
        "engineering": mat.get("score", 20),  # 20 base even without devops
        "organization": struct.get("organization_score", 50),  # 50 if not analyzed
        "documentation": qual.get("documentation_score", 30)  # 30 base score
    }
    
    # --- Viz ---
    output_dir = ctx.get("output_dir") or "."
    if not output_dir:
        output_dir = "."
    viz_path = os.path.join(output_dir, "scorecard.png")
    try:
        generate_dashboard(scores, viz_files, viz_path)
    except Exception as e:
        print(f"⚠️ Dashboard generation failed: {e}")
        viz_path = "N/A"

    return {
        "final_report": {
            "repo": ctx.get("repo_url"),
            "stack": stack,
            "scores": scores,
            "team": comm.get("author_stats", {}),
            "total_commits": comm.get("total_commits", 0),
            "files": detailed_files,
            "llm_detection": {"overall_percentage": overall_ai_percentage},  # Add AI detection summary
            "security": sec,
            "judge": judge,
            "maturity": mat,
            "commit_details": comm,
            "structure": struct,
            "repo_tree": repo_tree, # Full string of the tree
            "viz": viz_path
        }
    }

# ==========================================
# 2. Build Pipeline
# ==========================================

def build_pipeline(repo_url, output_dir, providers, gemini_key, progress_callback=None):
    g = SimpleLangGraph()
    
    g.add_node("clone", node_clone_repo)
    g.add_node("stack", node_stack_id)
    g.add_node("structure", node_structure_analysis)
    g.add_node("maturity", node_maturity_check)
    g.add_node("commits", node_commit_forensics)
    g.add_node("quality", node_quality_check)
    g.add_node("security", node_security_check)
    g.add_node("forensics", node_forensic_analysis)
    g.add_node("judge", node_ai_judge)
    g.add_node("aggregator", node_aggregator)
    
    # Edges (Parallel Execution)
    g.add_edge("clone", "stack")
    g.add_edge("clone", "structure")
    g.add_edge("clone", "maturity")
    g.add_edge("clone", "commits")
    g.add_edge("clone", "quality")
    g.add_edge("clone", "security")
    g.add_edge("clone", "forensics")
    g.add_edge("clone", "judge")
    
    # Edges (Aggregation)
    g.add_edge("stack", "aggregator")
    g.add_edge("structure", "aggregator")
    g.add_edge("maturity", "aggregator")
    g.add_edge("commits", "aggregator")
    g.add_edge("quality", "aggregator")
    g.add_edge("security", "aggregator")
    g.add_edge("forensics", "aggregator")
    g.add_edge("judge", "aggregator")
    
    return g.run({
        "repo_url": repo_url, 
        "output_dir": output_dir, 
        "llm_providers": providers,
        "gemini_key": gemini_key,
        "progress_callback": progress_callback
    })

# ==========================================
# 3. CSV Export Logic (WITH STRUCTURE FILE)
# ==========================================

def format_file_extensions(ext_string):
    if not ext_string: return "Unknown"
    
    mapping = {
        "py": "Python", "js": "JS", "ts": "TypeScript", 
        "jsx": "React", "tsx": "React", "css": "CSS", 
        "html": "HTML", "json": "Config", "md": "Docs", 
        "txt": "Text", "jpg": "Images", "png": "Images", 
        "java": "Java", "cpp": "C++"
    }
    
    parts = ext_string.split(", ")
    clean_types = set()
    for p in parts:
        ext = p.split(" ")[0]
        readable = mapping.get(ext, ext.upper())
        clean_types.add(readable)
        
    return ", ".join(sorted(clean_types))

def clean_winner_text(text):
    if not text or "None" in text: return "None"
    if "Led" in text:
        parts = text.split("Led ")
        name = parts[0].strip(" (")
        count = parts[1].strip(")")
        return f"{name} (Top for {count})"
    return text

def save_csv_results(output_dir, team_name, data):
    # Validate output_dir
    if not output_dir:
        output_dir = "."
    
    scores = data.get("scores", {})
    judge = data.get("judge", {})
    mat = data.get("maturity", {})
    struct = data.get("structure", {})
    comm = data.get("commit_details", {})
    sec = data.get("security", {})
    
    def clean_text(text):
        return str(text).replace("\n", " | ").replace("\r", "").strip()

    # --- SAVE REPO STRUCTURE TO TEXT FILE ---
    tree_content = data.get("repo_tree", "Tree generation failed.")
    structure_file = os.path.join(output_dir, "repository_structure.txt")
    try:
        with open(structure_file, "w", encoding="utf-8") as f:
            f.write(tree_content)
    except Exception as e:
        print(f"⚠️ Failed to save structure file: {e}")

    # --- PROCESS AUTHOR STATS ---
    author_stats = comm.get("author_stats", {})
    consistency = comm.get("consistency_stats", {})
    
    sorted_authors = sorted(author_stats.items(), key=lambda x: x[1]['commits'], reverse=True)
    
    breakdown_parts = []
    for name, stats in sorted_authors:
        commits = stats.get('commits', 0)
        days = stats.get('active_days_count', 0)
        raw_files = stats.get('top_file_types', '')
        readable_files = format_file_extensions(raw_files)
        
        part = f"{name}: {commits} commits (Active {days}d). Focus: {readable_files}"
        breakdown_parts.append(part)
        
    contribution_string = " | ".join(breakdown_parts)

    score_row = {
        # --- IDENTITY ---
        "Team_Name": team_name,
        "Repo_URL": data.get("repo"),
        "Tech_Stack": ", ".join(data.get("stack", [])),
        
        # --- SCORES (RENAMED) ---
        # --- SCORES (RENAMED) ---
        "TOTAL_SCORE": round(sum([
            scores.get('originality', 0) * 0.15,
            scores.get('implementation', 0) * 0.25,
            scores.get('engineering', 0) * 0.15,
            scores.get('security', 0) * 0.10,
            scores.get('quality', 0) * 0.10,
            scores.get('organization', 0) * 0.05,
            scores.get('effort', 0) * 0.20
        ]), 1),
        
        "Implementation": round(scores.get('implementation', 0), 1),
        "Originality": round(scores.get('originality', 0), 1),
        "Engineering": round(scores.get('engineering', 0), 1),
        "Code_Quality": round(scores.get('quality', 0), 1),
        "Security": round(scores.get('security', 0), 1),
        "Organization": round(scores.get('organization', 0), 1),
        "Effort": round(scores.get('effort', 0), 1),
        "Mean_Relevance": round(comm.get("total_relevance", 0) / max(1, comm.get("total_commits", 1)), 2),

        # --- AI FEEDBACK ---
        "AI_Pros": clean_text(judge.get("positive_feedback", "")),
        "AI_Cons": clean_text(judge.get("constructive_feedback", "")),
        
        # --- FORENSICS & ACTIVITY ---
        "Total_Commits": comm.get("total_commits", 0),
        "Branch_Count": comm.get("branch_count", 0),
        "Branches": ", ".join(comm.get("branches", [])),
        "Dummy_Commits": comm.get("dummy_commits", 0),
        "Team_Size": len(author_stats),
        "Contribution_Summary": contribution_string,
        
        # --- PERIOD WINNERS ---
        "Top_Daily": clean_winner_text(consistency.get("top_daily", "N/A")),
        "Top_Weekly": clean_winner_text(consistency.get("top_weekly", "N/A")),
        "Top_Monthly": clean_winner_text(consistency.get("top_monthly", "N/A")),

        # --- ENGINEERING DETAILS ---
        "Architecture": struct.get("architecture", "Unknown"),
        "DevOps_Tools": ", ".join(mat.get("devops_tools", [])),
        "Sec_Leaks": sec.get("leak_count", 0),
        "Is_Deployable": mat.get("is_deployable", False),
        
        # --- LINKS ---
        "Scorecard_Image": os.path.abspath(os.path.join(output_dir, "scorecard.png")),
        "Structure_File": os.path.abspath(structure_file) # <--- NEW LINK
    }
    
    scorecard_path = os.path.join(output_dir, "scorecard.csv")
    with open(scorecard_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=score_row.keys())
        writer.writeheader()
        writer.writerow(score_row)

    # Save Files Analysis
    files = data.get("files", [])
    if files:
        files_path = os.path.join(output_dir, "files_analysis.csv")
        file_keys = ["filename", "risk", "ai_pct", "plag_pct", "match"]
        with open(files_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=file_keys)
            writer.writeheader()
            writer.writerows(files)

    return score_row

# ==========================================
# 4. Universal Batch Input Parser
# ==========================================

def parse_input_file(file_path):
    repos = []
    ext = os.path.splitext(file_path)[1].lower()
    
    print(f"📂 Parsing input file: {file_path} ({ext})")
    
    try:
        # --- EXCEL FORMAT ---
        if ext in ['.xlsx', '.xls']:
            try:
                import pandas as pd
            except ImportError:
                print("❌ Missing dependency: pandas. Please run 'pip install pandas openpyxl'")
                return []
            
            df = pd.read_excel(file_path)
            df.columns = df.columns.str.strip().str.lower()
            data = df.to_dict(orient='records')
            
            for row in data:
                url = row.get('repo url') or row.get('url') or row.get('repo')
                name = row.get('team name') or row.get('name') or row.get('team') or f"Team-{len(repos)+1}"
                if url and pd.notna(url) and str(url).strip().startswith('http'):
                    repos.append({"name": str(name).strip(), "url": str(url).strip()})

        # --- JSON FORMAT ---
        elif ext == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for entry in data:
                        clean = {k.strip().lower(): v for k, v in entry.items()}
                        url = clean.get('repo url') or clean.get('url') or clean.get('repo')
                        name = clean.get('team name') or clean.get('name') or clean.get('team') or "Unknown"
                        if url:
                            repos.append({"name": name, "url": url.strip()})
        
        # --- CSV / TEXT FORMAT ---
        else:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                sample = f.read(1024)
                f.seek(0)
                has_header = csv.Sniffer().has_header(sample) if ',' in sample else False
                
                if has_header or ',' in sample:
                    reader = csv.DictReader(f)
                    for row in reader:
                        clean = {k.strip().lower(): v.strip() for k, v in row.items()}
                        url = clean.get('repo url') or clean.get('url') or clean.get('repo')
                        name = clean.get('team name') or clean.get('name') or clean.get('team') or f"Team-{len(repos)+1}"
                        if url:
                            repos.append({"name": name, "url": url})
                else:
                    print("ℹ️  Treating file as raw URL list.")
                    for line in f:
                        line = line.strip()
                        if line and line.startswith("http"):
                            repos.append({"name": f"Team-{len(repos)+1}", "url": line})

    except Exception as e:
        print(f"❌ Error parsing input file: {e}")
        return []

    return repos

# ==========================================
# 5. Batch Runner (SAFE SAVE)
# ==========================================

def run_batch_mode(file_path, output_dir, providers, gemini_key):
    repos = parse_input_file(file_path)
    
    if not repos:
        print("❌ No valid repositories found in input file.")
        return

    print(f"📋 Found {len(repos)} teams to evaluate.\n")
    
    results = []
    failed = []
    
    for i, team in enumerate(repos):
        team_name = team['name']
        url = team['url']
        
        print(f"\n{'='*60}")
        print(f"⏳ Processing {i+1}/{len(repos)}: {team_name}")
        print(f"{'='*60}")
        
        safe_name = "".join([c if c.isalnum() else "_" for c in team_name])
        team_out_dir = os.path.join(output_dir, safe_name)
        os.makedirs(team_out_dir, exist_ok=True)
        
        try:
            res = build_pipeline(url, team_out_dir, providers, gemini_key)
            data = res.get("final_report", {})
            score_row = save_csv_results(team_out_dir, team_name, data)
            results.append(score_row)
            print(f"✅ Finished {team_name} (Score: {score_row['TOTAL_SCORE']})")
        except Exception as e:
            print(f"❌ Failed {team_name}: {e}")
            failed.append(team_name)

    if results:
        keys = list(results[0].keys())
        results.sort(key=lambda x: float(x['TOTAL_SCORE']), reverse=True)
        for idx, r in enumerate(results):
            r["Rank"] = idx + 1
        if "Rank" not in keys: keys.insert(0, "Rank")

        # --- SAFE SAVE LOGIC ---
        lb_filename = "LEADERBOARD.csv"
        lb_path = os.path.join(output_dir, lb_filename)
        
        counter = 1
        while True:
            try:
                # Check permission by opening in append mode
                with open(lb_path, "a", newline="", encoding="utf-8-sig"): pass
                
                # Write file
                with open(lb_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(results)
                print(f"\n🎉 Batch Complete! Leaderboard saved to: {os.path.abspath(lb_path)}")
                break
            except PermissionError:
                print(f"⚠️  File '{lb_filename}' is open. Saving to new file...")
                lb_filename = f"LEADERBOARD_{counter}.csv"
                lb_path = os.path.join(output_dir, lb_filename)
                counter += 1
            except Exception as e:
                print(f"❌ Critical Error saving leaderboard: {e}")
                break

    if failed:
        print(f"⚠️  Failed Teams: {', '.join(failed)}")

# ==========================================
# 6. Helpers & Printer
# ==========================================

def print_row(col1, col2, col3="", col4=""):
    print(f"  {col1:<25} | {col2:<15} | {col3:<15} | {col4}")

def rate(val, high=80, low=50):
    return "✅ Excellent" if val > high else "⚠️ Needs Work" if val > low else "❌ Critical"

def print_single_report(data):
    scores = data.get("scores", {})
    judge = data.get("judge", {})
    mat = data.get("maturity", {})
    struct = data.get("structure", {})
    comm = data.get("commit_details", {})
    consistency = comm.get("consistency_stats", {})
    
    print("\n" * 2)
    print("="*80)
    print(f"       🏆  HACKATHON EVALUATION REPORT  🏆")
    print("="*80)
    print(f"\n[1] PROJECT OVERVIEW")
    print(f"  📂 Repository:       {data.get('repo')}")
    print(f"  🤖 Project Name:     {judge.get('project_name', 'Unknown')}")
    print(f"  🛠️  Tech Stack:       {', '.join(data.get('stack', []))}")

    print(f"\n[2] JUDGE'S SCORECARD (0-100)")
    print(f"  {'METRIC':<20} {'SCORE':<10} {'STATUS'}")
    print(f"  {'-'*20} {'-'*10} {'-'*20}")
    print(f"  Originality         {scores.get('originality', 0):<10.1f} {rate(scores.get('originality', 0), 70, 40)}")
    print(f"  Implementation      {scores.get('implementation', 0):<10.1f} {rate(scores.get('implementation', 0), 80, 50)}")
    print(f"  Engineering         {scores.get('engineering', 0):<10.1f} {rate(scores.get('engineering', 0), 60, 30)}")
    print(f"  Structure/Org       {scores.get('organization', 0):<10.1f} {rate(scores.get('organization', 0), 80, 60)}")
    print(f"  Code Quality        {scores.get('quality', 0):<10.1f} {rate(scores.get('quality', 0), 60, 40)}")
    print(f"  Security            {scores.get('security', 0):<10.1f} {rate(scores.get('security', 0), 99, 80)}")

    if judge.get("project_name") != "Unknown":
        print(f"\n[3] 🧠 AI JUDGE FEEDBACK")
        print(f"  👍 Pros:  \"{judge.get('positive_feedback')}\"")
        print(f"  💡 Cons:  \"{judge.get('constructive_feedback')}\"")
        print(f"  ⚖️  Verdict: {judge.get('verdict')}")

    print(f"\n[4] 🏗️  ARCHITECTURE & ORGANIZATION")
    print(f"  🏛️  Detected Pattern:  {struct.get('architecture', 'Unknown')}")
    depth = struct.get("max_depth", 0)
    print(f"  ✅ Good Directory Organization ({depth} levels).")

    print(f"\n[5] 🚀 ENGINEERING MATURITY")
    print(f"  📦 Deployable?       {'✅ Yes (Docker/Cloud)' if mat.get('is_deployable') else '❌ No (Local only)'}")
    print(f"  🧪 Test Suite:       {mat.get('test_files', 0)} files / {mat.get('test_lines', 0)} lines")

    sec = data.get("security", {})
    if sec.get("leak_count", 0) > 0:
        print(f"\n[6] 🔐 SECURITY ALERTS")
        print(f"  ⚠️  Found {sec['leak_count']} secret leaks!")
    else:
        print(f"\n[6] 🔐 SECURITY STATUS: ✅ Safe")

    print(f"\n[7] 👥 DETAILED TEAM ACTIVITY")
    print(f"  📅 Top Daily Contributor:   {clean_winner_text(consistency.get('top_daily', 'N/A'))}")
    print(f"  🌿 Branches Detected:       {comm.get('branch_count', 0)} ({', '.join(comm.get('branches', [])[:3])}...)")
    
    if comm.get("dummy_commits", 0) > 0:
        print(f"  ⚠️  WARNING: {comm['dummy_commits']} dummy/empty commits detected!")
        
    author_stats = comm.get("author_stats", {})
    if author_stats:
        sorted_team = sorted(author_stats.items(), key=lambda x: x[1]['commits'], reverse=True)
        print(f"\n  {'AUTHOR':<20} | {'COMMITS':<8} | {'ACTIVE':<12} | {'FOCUS AREA'}")
        print(f"  {'-'*20} | {'-'*8} | {'-'*12} | {'-'*20}")
        for name, stats in sorted_team:
             files = format_file_extensions(stats.get('top_file_types', ''))
             print(f"  {name[:20]:<20} | {str(stats.get('commits',0)):<8} | {str(stats.get('active_days_count',0))+' days':<12} | {files}")
             
    # Print Branch Activity Summary
    branch_act = comm.get("branch_activity", {})
    if branch_act:
        print(f"\n  🌿 Branch-wise Activity:")
        for branch, authors in branch_act.items():
            auth_str = ", ".join([f"{a}:{c}" for a,c in authors.items()])
            if len(auth_str) > 60: auth_str = auth_str[:60] + "..."
            print(f"     - {branch}: {auth_str}")

    print(f"\n[8] 📂 REPOSITORY STRUCTURE")
    print(data.get("repo_tree", "  (Tree generation failed)"))
    print("\n" + "="*80)

# ==========================================
# 7. Main Execution
# ==========================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", help="Override the default INPUT_FILE path")
    parser.add_argument("--out", default="./report", help="Output dir")
    parser.add_argument("--providers", nargs="+", default=[], help="LLM providers")
    parser.add_argument("--batch", action="store_true", help="Force batch mode")
    
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        print("❌ FATAL: GEMINI_API_KEY not found in .env file.")
        print("   Please create a .env file with: GEMINI_API_KEY=your_key")
        sys.exit(1)

    # Use CLI arg if provided, else use config
    target_input = args.input if args.input else INPUT_FILE
    if not target_input.startswith("http"):
        target_input = os.path.abspath(target_input)

    try:
        is_url = target_input.startswith("http")
        is_file = os.path.exists(target_input)
        
        if is_file:
            print(f"🚀 Running BATCH MODE using file: {target_input}")
            run_batch_mode(target_input, args.out, args.providers, gemini_key)
        elif is_url:
            print(f"🚀 Running SINGLE MODE on URL: {target_input}")
            res = build_pipeline(target_input, args.out, args.providers, gemini_key)
            data = res.get("final_report", {})
            print_single_report(data)
            save_csv_results(args.out, "Project", data)
            print(f"\n[SUCCESS] Report & CSVs saved to {os.path.abspath(args.out)}")
        else:
            print(f"❌ Error: Input '{target_input}' is invalid.")

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()