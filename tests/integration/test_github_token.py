
import httpx
import asyncio

import os

def get_env_variable(var_name):
    try:
        with open(".env", "r") as f:
            for line in f:
                if line.startswith(var_name):
                    return line.split("=")[1].strip()
    except FileNotFoundError:
        pass
    return os.getenv(var_name)

TOKEN = get_env_variable("GH_API_KEY")

async def test_token():
    async with httpx.AsyncClient() as client:
        # Test 1: Rate Limit endpoint (good for auth check)
        print("Testing token against rate_limit...")
        resp = await client.get("https://api.github.com/rate_limit", headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        })
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("Token works for rate_limit.")
            print("Rate Limit:", resp.json()["rate"])
        else:
            print("Token failed rate_limit check:", resp.text)
            
        # Test 2: Fetch specific repo
        print("\nTesting fetch of octocat/Spoon-Knife...")
        resp = await client.get("https://api.github.com/repos/octocat/Spoon-Knife/languages", headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        })
        print(f"Status: {resp.status_code}")
        print(resp.text[:200])

if __name__ == "__main__":
    asyncio.run(test_token())
