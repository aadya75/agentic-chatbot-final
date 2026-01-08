"""
Test script to verify Google servers work standalone before connecting to client
Run this first to diagnose issues with Gmail, Drive, and Calendar servers

UPDATED FOR NEW FOLDER STRUCTURE:
backend/
├── mcp_servers/
│   ├── gmail_server.py
│   ├── drive_server.py
│   └── calendar_server.py
├── credentials/
│   ├── credentials.json
│   └── token.json
└── scripts/
    └── test_servers.py (this file)
"""

import sys
import os
import subprocess
from pathlib import Path

def test_server_import(server_path, server_name, credentials_dir):
    """Test if a server file exists and can be imported"""
    print(f"\n{'='*60}")
    print(f"Testing {server_name}")
    print('='*60)
    
    # Check if file exists
    if not os.path.exists(server_path):
        print(f"❌ File not found: {server_path}")
        return False
    
    print(f"✓ File exists: {server_path}")
    
    # Check if credentials.json and token.json exist in credentials directory
    credentials_path = credentials_dir / "credentials.json"
    token_path = credentials_dir / "token.json"
    
    if not credentials_path.exists():
        print(f"❌ Missing credentials.json at: {credentials_path}")
        print(f"   You need to download OAuth credentials from Google Cloud Console")
        print(f"   and place it in: {credentials_dir}")
        return False
    else:
        print(f"✓ credentials.json found at: {credentials_path}")
    
    if not token_path.exists():
        print(f"⚠️  Missing token.json at: {token_path}")
        print(f"   You need to run the authentication script first")
        print(f"   Run: python backend/scripts/generate_all_tokens.py")
        return False
    else:
        print(f"✓ token.json found at: {token_path}")
    
    # Try to run the server briefly to check for syntax errors
    print(f"\n🔍 Testing if {server_name} can start...")
    try:
        # Start the server process from backend directory
        backend_dir = Path(server_path).parent.parent
        process = subprocess.Popen(
            ['python', str(server_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            cwd=str(backend_dir)  # Run from backend dir so relative paths work
        )
        
        # Give it a moment to start or fail
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            # If it times out, that's actually good - it means it's running
            process.kill()
            stdout, stderr = process.communicate()
            print(f"✅ {server_name} started successfully (process running)")
            return True
        
        # If it exited immediately, check for errors
        if process.returncode != 0:
            print(f"❌ {server_name} exited with error code {process.returncode}")
            if stderr:
                print(f"   Error output:\n{stderr.decode()}")
            return False
        else:
            print(f"✅ {server_name} can run")
            return True
            
    except Exception as e:
        print(f"❌ Error testing {server_name}: {e}")
        return False

def main():
    print("="*60)
    print("Google MCP Servers - Diagnostic Test")
    print("="*60)
    
    # Get paths dynamically from this script's location
    # This file is in: backend/scripts/test_servers.py
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parent
    mcp_servers_dir = backend_dir / "mcp_servers"
    credentials_dir = backend_dir / "credentials"
    
    print(f"\n📁 Detected paths:")
    print(f"   Backend: {backend_dir}")
    print(f"   MCP Servers: {mcp_servers_dir}")
    print(f"   Credentials: {credentials_dir}")
    
    # Define server paths
    servers = {
        "Gmail": mcp_servers_dir / "gmail_server.py",
        "Drive": mcp_servers_dir / "google_drive_server.py",
        "Calendar": mcp_servers_dir / "google_calendar_server.py",
    }
    
    # Check if directories exist
    if not mcp_servers_dir.exists():
        print(f"\n❌ ERROR: MCP servers directory not found at {mcp_servers_dir}")
        print("   Make sure you're running this from backend/scripts/")
        return
    
    if not credentials_dir.exists():
        print(f"\n❌ ERROR: Credentials directory not found at {credentials_dir}")
        print(f"   Creating it now...")
        credentials_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created {credentials_dir}")
        print(f"   Please place your credentials.json there")
    
    results = {}
    for name, path in servers.items():
        results[name] = test_server_import(str(path), name, credentials_dir)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All servers are ready!")
        print("\nNext steps:")
        print("1. Run your client to connect all servers")
        print("2. Start building your FastAPI backend (backend/api/main.py)")
    else:
        print("\n⚠️  Some servers have issues. Fix them before proceeding.")
        print("\nCommon fixes:")
        print("1. Place credentials.json in: backend/credentials/")
        print("2. Run: python backend/scripts/generate_all_tokens.py")
        print("3. Install required packages:")
        print("   pip install mcp google-auth google-auth-oauthlib google-api-python-client")
        print("4. Update all server files with new path code (check the path_updates artifact)")

if __name__ == "__main__":
    main()