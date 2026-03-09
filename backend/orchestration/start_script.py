# start_server.py
import os
import subprocess
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set environment variables
env_vars = {
    'GOOGLE_OAUTH_CLIENT_ID': os.getenv('GOOGLE_OAUTH_CLIENT_ID', ''),
    'GOOGLE_OAUTH_CLIENT_SECRET': os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', ''),
    'USER_GOOGLE_EMAIL': os.getenv('USER_GOOGLE_EMAIL', ''),
    'OAUTHLIB_INSECURE_TRANSPORT': '1'
}

print("🚀 Starting Google Workspace MCP Server...")
print("Environment Variables:")
for key, value in env_vars.items():
    if value:
        print(f"  {key}: ✓ Set")
    else:
        print(f"  {key}: ✗ Not Set")

# Prepare command
cmd = ['uvx', 'workspace-mcp', '--tools', 'gmail','calendar', '--transport', 'streamable-http']

# Run with environment variables
subprocess.run(cmd, env={**os.environ, **env_vars})