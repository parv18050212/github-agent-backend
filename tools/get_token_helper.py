"""
Google OAuth Token Helper
Helps you get a Google ID token for testing
"""
import webbrowser
import json

CYAN = '\033[96m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BLUE = '\033[94m'
GREEN = '\033[92m'

def print_header(text):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{text:^70}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

print_header("Google OAuth Token Helper")

print(f"{CYAN}To get a Google ID token, you need to:{RESET}\n")

print("1️⃣  Configure Google OAuth in Supabase:")
print("   a. Go to your Supabase project dashboard")
print("   b. Navigate to Authentication → Providers")
print("   c. Enable Google provider")
print("   d. Enter your Google OAuth credentials")
print(f"      {YELLOW}(Get from: https://console.cloud.google.com/apis/credentials){RESET}")

print("\n2️⃣  Use one of these methods to get a token:\n")

print(f"{GREEN}Method A: Using Supabase Auth UI (Frontend){RESET}")
print("   Create a simple HTML file:")
print(f"""
{CYAN}<!DOCTYPE html>
<html>
<head>
    <title>Get Google Token</title>
    <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
</head>
<body>
    <h1>Click to Login with Google</h1>
    <button onclick="login()">Login with Google</button>
    <div id="token"></div>
    
    <script>
        const supabase = window.supabase.createClient(
            'YOUR_SUPABASE_URL',
            'YOUR_SUPABASE_ANON_KEY'
        );
        
        async function login() {{
            const {{ data, error }} = await supabase.auth.signInWithOAuth({{
                provider: 'google',
                options: {{
                    redirectTo: window.location.origin
                }}
            }});
        }}
        
        // After redirect, get the token
        supabase.auth.onAuthStateChange((event, session) => {{
            if (session) {{
                const idToken = session.access_token;
                document.getElementById('token').innerHTML = 
                    '<h2>Your ID Token:</h2><textarea rows="5" cols="80">' + 
                    idToken + '</textarea>';
                console.log('ID Token:', idToken);
            }}
        }});
    </script>
</body>
</html>{RESET}
""")

print(f"\n{GREEN}Method B: Using cURL (if you have a refresh token){RESET}")
print(f"""
{CYAN}curl -X POST 'https://YOUR_PROJECT.supabase.co/auth/v1/token?grant_type=refresh_token' \\
  -H "Content-Type: application/json" \\
  -H "apikey: YOUR_ANON_KEY" \\
  -d '{{"refresh_token": "YOUR_REFRESH_TOKEN"}}'{RESET}
""")

print(f"\n{GREEN}Method C: From Browser Console (if already logged in){RESET}")
print(f"""
   1. Login to your app with Supabase Auth
   2. Open browser DevTools (F12)
   3. Go to Console tab
   4. Run: {CYAN}supabase.auth.getSession().then(r => console.log(r.data.session.access_token)){RESET}
   5. Copy the token
""")

print(f"\n{YELLOW}⚠️  Important Notes:{RESET}")
print("   • Tokens expire (usually in 1 hour)")
print("   • Never commit tokens to git")
print("   • For production, use proper OAuth flow")

print(f"\n{BLUE}{'='*70}{RESET}")
print(f"{CYAN}Once you have the token, run:{RESET}")
print(f"   {GREEN}python test_real_auth.py{RESET}")
print(f"{BLUE}{'='*70}{RESET}\n")

# Ask if user wants to open Supabase dashboard
choice = input(f"{CYAN}Open Supabase dashboard in browser? (y/n): {RESET}").lower()
if choice == 'y':
    project_url = input(f"{CYAN}Enter your Supabase project URL (or press Enter to skip): {RESET}")
    if project_url:
        # Extract project ID and open dashboard
        if 'supabase.co' in project_url:
            project_id = project_url.split('//')[1].split('.')[0]
            dashboard_url = f"https://supabase.com/dashboard/project/{project_id}/auth/providers"
            print(f"{GREEN}Opening Supabase dashboard...{RESET}")
            webbrowser.open(dashboard_url)
        else:
            print(f"{YELLOW}Invalid URL format{RESET}")
