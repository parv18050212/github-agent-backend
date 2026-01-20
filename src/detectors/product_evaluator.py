import os
import json
from google import genai
from google.genai import types
from src.utils.repo_summary import generate_repo_summary

def evaluate_product_logic(repo_path: str, api_key: str = None) -> dict:
    # 1. Validation
    if not api_key:
        return {
            "project_name": "Unknown", 
            "description": "No Gemini API Key provided.",
            "features": [],
            "score": 0,
            "feedback": "Skipped"
        }
    
    if not repo_path or not os.path.exists(repo_path):
        print(f"⚠️ Product evaluation skipped: invalid repo_path ({repo_path})")
        return {
            "project_name": "Unknown",
            "description": "Repository path not available.",
            "features": [],
            "implementation_score": 50,
            "positive_feedback": "Unable to analyze - repository not cloned",
            "constructive_feedback": "Repository cloning failed",
            "verdict": "Analysis Incomplete"
        }

    print("      🧠 Generating Codebase Summary for Gemini 2.5...")
    context = generate_repo_summary(repo_path)
    
    # 2. Configure Gemini API
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        You are a Senior CTO judging a Hackathon. Analyze the following codebase summary.
        
        OUTPUT MUST BE VALID JSON ONLY. NO MARKDOWN.
        
        JSON Schema:
        {{
            "project_name": "inferred name",
            "description": "1 sentence summary",
            "features": ["list", "of", "features"],
            "tech_stack_observed": ["list", "of", "libs"],
            "implementation_score": (0-100 int),
            "positive_feedback": "string",
            "constructive_feedback": "string",
            "verdict": "Production Ready / Prototype / Broken"
        }}

        CODEBASE CONTEXT:
        {context}
        """

        # 3. Call API
        print("      🚀 Sending to Gemini 2.0 Flash...")
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        # 4. Parse Response
        if response.text:
            return json.loads(response.text)
        return {}

    except Exception as e:
        print(f"      ❌ Gemini Error: {e}")
        # Return defaults instead of error state when Gemini fails
        return {
            "project_name": "Unknown",
            "description": "Analysis unavailable due to API error",
            "features": [],
            "tech_stack_observed": [],
            "implementation_score": 50,  # Neutral score instead of 0
            "positive_feedback": "Project structure appears organized.",
            "constructive_feedback": "Unable to perform detailed analysis. Please verify API configuration.",
            "verdict": "Analysis Incomplete"
        }
