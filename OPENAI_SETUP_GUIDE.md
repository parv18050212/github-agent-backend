# OpenAI Setup Guide

## Quick Start

### 1. Install OpenAI Package
```bash
pip install openai
```

### 2. Get Your API Key
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key (starts with `sk-proj-...`)

### 3. Configure Environment
Edit `proj-github agent/.env` and add:
```bash
OPENAI_API_KEY=sk-proj-your-actual-key-here
```

### 4. Test the Setup
```bash
cd "proj-github agent"
python test_openai_migration.py
```

## Expected Output
```
============================================================
OpenAI Migration Test Suite
============================================================

[Test] Import OpenAI Library
------------------------------------------------------------
✅ OpenAI library imported successfully

[Test] Check API Key
------------------------------------------------------------
✅ OPENAI_API_KEY is configured (length: 164)

[Test] Import Product Evaluator
------------------------------------------------------------
✅ Product evaluator imported successfully

[Test] Test API Call
------------------------------------------------------------
🚀 Testing OpenAI API connection...
✅ OpenAI API call successful: {"message": "API test successful"}

============================================================
Results: 4/4 tests passed
============================================================

🎉 All tests passed! Migration successful.
```

## Troubleshooting

### Error: "No module named 'openai'"
**Solution:** Install the package
```bash
pip install openai
```

### Error: "OPENAI_API_KEY not configured"
**Solution:** Add your API key to `.env` file
```bash
OPENAI_API_KEY=sk-proj-...
```

### Error: "Incorrect API key provided"
**Solution:** 
1. Verify your API key at https://platform.openai.com/api-keys
2. Make sure you copied the entire key
3. Check for extra spaces in the .env file

### Error: "Rate limit exceeded"
**Solution:** 
1. Check your OpenAI usage at https://platform.openai.com/usage
2. Upgrade your plan if needed
3. Add delays between API calls for batch processing

## Cost Management

### Current Model: gpt-4o-mini
- Input: $0.150 per 1M tokens
- Output: $0.600 per 1M tokens

### Typical Analysis Cost
- ~2,000 tokens per repository
- ~$0.0003 per analysis
- 100 repos = ~$0.03

### Switch to Cheaper Model
Edit `src/detectors/product_evaluator.py` line 56:
```python
model="gpt-3.5-turbo",  # Cheaper option
```

### Switch to Better Model
```python
model="gpt-4o",  # Higher quality
```

## API Key Security

### ⚠️ Important Security Notes
1. **Never commit** `.env` file to git
2. **Never share** your API key publicly
3. **Rotate keys** regularly
4. **Use environment variables** in production

### Production Setup
For production, use environment variables instead of .env:
```bash
export OPENAI_API_KEY=sk-proj-...
```

Or use a secrets manager (AWS Secrets Manager, Azure Key Vault, etc.)

## Testing Your Analysis

### Test Single Repository
```bash
cd "proj-github agent"
python -m src.core.agent --input https://github.com/torvalds/linux
```

### Test Batch Analysis
Create a test file `test_repos.csv`:
```csv
Team Name,Repository URL
Test Team,https://github.com/user/repo
```

Run:
```bash
python -m src.core.agent --input test_repos.csv --out reports
```

## Monitoring Usage

Check your OpenAI usage:
1. Go to https://platform.openai.com/usage
2. View daily/monthly usage
3. Set up billing alerts

## Support

- OpenAI Documentation: https://platform.openai.com/docs
- API Reference: https://platform.openai.com/docs/api-reference
- Community Forum: https://community.openai.com
