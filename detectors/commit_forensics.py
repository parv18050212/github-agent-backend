

# from typing import List, Dict, Any
# from utils.git_utils import get_commit_history

# def analyze_commits(repo_path: str) -> Dict[str, Any]:
#     # 1. Get History (Ensure git_utils.py clone_repo has depth=None as discussed)
#     commits = get_commit_history(repo_path, max_commits=800)
    
#     suspicious_commits = []
#     author_stats = {} # New: Track churn per author

#     for c in commits:
#         # --- Suspicious Checks ---
#         added = c.get("added", 0)
#         files = c.get("files", [])
#         msg = (c.get("message") or "").lower()
#         reasons = []
        
#         if added > 500 or len(files) > 50:
#             reasons.append("large_add")
#         if any(tok in msg for tok in ["copilot", "generated", "autogen", "ai-suggest", "gpt"]):
#             reasons.append("message_flag")
        
#         if reasons:
#             suspicious_commits.append({
#                 "hexsha": c["hexsha"],
#                 "reasons": reasons,
#                 "msg": c.get("message"),
#                 "datetime": c.get("datetime")
#             })

#         # --- Team Balance Logic (New) ---
#         auth = c.get("author", "Unknown")
#         if auth not in author_stats:
#             author_stats[auth] = {"commits": 0, "lines_changed": 0}
        
#         author_stats[auth]["commits"] += 1
#         author_stats[auth]["lines_changed"] += (added + c.get("deleted", 0))

#     # Calculate Suspicious Score
#     score = min(1.0, len(suspicious_commits) / max(1, len(commits)))

#     return {
#         "score": score,
#         "suspicious_commits": suspicious_commits,
#         "total_commits": len(commits),
#         "author_stats": author_stats # Return team stats
#     }








import math
from typing import Dict, Any, List
from datetime import datetime
from collections import defaultdict, Counter
import git
from git import Repo

def _calculate_entropy(text: str) -> float:
    if not text: return 0.0
    prob = [float(text.count(c)) / len(text) for c in dict.fromkeys(list(text))]
    return -sum([p * math.log(p) / math.log(2.0) for p in prob])

def analyze_commits(repo_path: str) -> Dict[str, Any]:
    try:
        repo = Repo(repo_path)
    except Exception as e:
        return {"error": str(e), "total_commits": 0}

    # --- 1. BRANCH ANALYSIS ---
    try:
        local_branches = [h.name for h in repo.heads]
        remote_branches = [r.name for r in repo.remotes.origin.refs] if repo.remotes else []
        all_branches = list(set(local_branches + remote_branches))
    except:
        all_branches = ["master"]

    # Branch-wise Author Breakdown
    # Structure: {'main': {'Alice': 10, 'Bob': 2}, 'dev': {'Alice': 5}}
    branch_stats = defaultdict(Counter)
    
    # We analyze up to 100 commits per branch to map author activity on that specific branch
    for b in repo.heads:
        try:
            for c in repo.iter_commits(b.name, max_count=100):
                branch_stats[b.name][c.author.name] += 1
        except:
            pass

    # --- 2. DEEP FORENSICS SETUP ---
    try:
        # Get full history from all references
        raw_commits = list(repo.iter_commits('--all', max_count=5000))
    except:
        raw_commits = []

    # Storage for analysis
    author_stats = defaultdict(lambda: {
        "commits": 0, "lines_added": 0, "lines_deleted": 0, 
        "active_days": set(), "file_types": Counter()
    })
    
    # Period Trackers: { '2023-10-01': {'Alice': 5, 'Bob': 1} }
    daily_activity = defaultdict(Counter)
    weekly_activity = defaultdict(Counter)
    monthly_activity = defaultdict(Counter)
    
    suspicious_commits = []
    dummy_commit_count = 0
    prev_commit = None
    
    # Sort Oldest -> Newest for proper timeline analysis
    raw_commits.sort(key=lambda x: x.committed_datetime)

    for c in raw_commits:
        author = c.author.name
        date = c.committed_datetime
        msg = c.message.strip()
        
        # Keys for aggregation
        day_key = date.strftime('%Y-%m-%d')
        week_key = date.strftime('%Y-W%U')
        month_key = date.strftime('%Y-%m')
        
        # A. PERIOD AGGREGATION
        daily_activity[day_key][author] += 1
        weekly_activity[week_key][author] += 1
        monthly_activity[month_key][author] += 1
        
        # B. AUTHOR TOTALS
        author_stats[author]["commits"] += 1
        author_stats[author]["active_days"].add(day_key)
        
        # C. FILE & STATS ANALYSIS
        added, deleted = 0, 0
        try:
            # Check what files changed
            for file_path, stats in c.stats.files.items():
                ext = file_path.split('.')[-1] if '.' in file_path else 'no_ext'
                author_stats[author]["file_types"][ext] += 1
                added += stats.get('insertions', 0)
                deleted += stats.get('deletions', 0)
        except:
            pass

        author_stats[author]["lines_added"] += added
        author_stats[author]["lines_deleted"] += deleted

        # D. FORENSIC CHECKS
        is_suspicious = False
        reasons = []

        # 1. Dummy Commit (0 files changed)
        if added == 0 and deleted == 0:
            is_suspicious = True
            reasons.append("Empty/Dummy Commit")
            dummy_commit_count += 1
            
        # 2. Repeated Commit (Same msg + Same content change + Close time)
        if prev_commit:
            time_diff = (date - prev_commit.committed_datetime).total_seconds()
            same_msg = msg == prev_commit.message.strip()
            
            # If same message AND < 5 mins apart
            if same_msg and time_diff < 300:
                is_suspicious = True
                reasons.append("Repeated Commit (Spam)")
            
            # If superhuman speed (< 10s)
            if time_diff < 10:
                is_suspicious = True
                reasons.append("Superhuman Speed (<10s)")

        if is_suspicious:
            suspicious_commits.append({
                "hash": c.hexsha[:7],
                "author": author,
                "msg": msg[:30],
                "reasons": reasons
            })

        prev_commit = c

    # --- 3. CALCULATE "WINNERS" FOR PERIODS ---
    def get_period_winners(activity_dict):
        """Returns who won the most periods (e.g., who was top contributor for the most days)"""
        winners = Counter()
        for period, counts in activity_dict.items():
            if counts:
                top_auth = counts.most_common(1)[0][0] # Get author with max commits that period
                winners[top_auth] += 1
        return winners.most_common(1)[0] if winners else ("None", 0)

    top_daily_winner, daily_wins = get_period_winners(daily_activity)
    top_weekly_winner, weekly_wins = get_period_winners(weekly_activity)
    top_monthly_winner, monthly_wins = get_period_winners(monthly_activity)

    # --- 4. FORMAT FINAL STATS ---
    final_author_stats = {}
    for auth, data in author_stats.items():
        # Get top 3 file types modified by this author
        top_files = [f"{ext} ({cnt})" for ext, cnt in data["file_types"].most_common(3)]
        
        final_author_stats[auth] = {
            "commits": data["commits"],
            "lines_changed": data["lines_added"] + data["lines_deleted"],
            "active_days_count": len(data["active_days"]),
            "top_file_types": ", ".join(top_files)
        }

    return {
        "total_commits": len(raw_commits),
        "branch_count": len(all_branches),
        "branches": all_branches,
        "branch_activity": {k: dict(v) for k, v in branch_stats.items()}, # Branch-wise breakdown
        "author_stats": final_author_stats,
        "dummy_commits": dummy_commit_count,
        "suspicious_list": suspicious_commits,
        
        # Period Winners
        "consistency_stats": {
            "top_daily": f"{top_daily_winner} (Led {daily_wins} days)",
            "top_weekly": f"{top_weekly_winner} (Led {weekly_wins} weeks)",
            "top_monthly": f"{top_monthly_winner} (Led {monthly_wins} months)"
        }
    }