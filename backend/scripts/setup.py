#!/usr/bin/env python3
"""
Setup script for the agentic chatbot backend.

This script helps with initial setup:
1. Creates necessary directories
2. Checks for required files
3. Validates environment variables
4. Tests MCP server connections
"""

import os
import sys
from pathlib import Path
import shutil

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def check_python_version():
    """Ensure Python 3.8+"""
    print_header("Checking Python Version")
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    print("✅ Python version is compatible")

def create_directories():
    """Create necessary directories"""
    print_header("Creating Directories")
    
    dirs = [
        BACKEND_DIR / "credentials",
        BACKEND_DIR / "logs",
        BACKEND_DIR / "data",
    ]
    
    for dir_path in dirs:
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created: {dir_path.relative_to(BACKEND_DIR.parent)}")
        else:
            print(f"✓  Exists: {dir_path.relative_to(BACKEND_DIR.parent)}")

def setup_env_file():
    """Setup .env file from .env.example"""
    print_header("Setting up Environment Variables")
    
    env_file = BACKEND_DIR / ".env"
    env_example = BACKEND_DIR / ".env.example"
    
    if env_file.exists():
        print("✓  .env file already exists")
        response = input("Do you want to overwrite it? (y/N): ")
        if response.lower() != 'y':
            print("Keeping existing .env file")
            return
    
    if env_example.exists():
        shutil.copy(env_example, env_file)
        print(f"✅ Created .env from .env.example")
        print("\n⚠️  IMPORTANT: Edit .env and add your API keys!")
        print(f"   File location: {env_file}")
    else:
        print("❌ .env.example not found")

def check_dependencies():
    """Check if required packages are installed"""
    print_header("Checking Dependencies")
    
    required_packages = [
        "fastapi",
        "uvicorn",
        "langchain",
        "langchain_groq",
        "google.auth",
        "pydantic",
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (missing)")
            missing.append(package)
    
    if missing:
        print("\n⚠️  Missing packages detected!")
        print("Install them with:")
        print("  pip install -r requirements.txt")
        return False
    
    print("\n✅ All dependencies installed")
    return True

def check_credentials():
    """Check for Google API credentials"""
    print_header("Checking Google API Credentials")
    
    creds_file = BACKEND_DIR / "credentials" / "credentials.json"
    
    if creds_file.exists():
        print("✅ credentials.json found")
    else:
        print("⚠️  credentials.json not found")
        print("\nTo get credentials:")
        print("1. Go to: https://console.cloud.google.com/")
        print("2. Create a new project (or select existing)")
        print("3. Enable Gmail, Drive, and Calendar APIs")
        print("4. Create OAuth 2.0 credentials")
        print("5. Download and save as:")
        print(f"   {creds_file}")

def check_env_variables():
    """Check if required environment variables are set"""
    print_header("Checking Environment Variables")
    
    # Try to load .env
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
    
    required_vars = {
        "GROQ_API_KEY": "Groq API key for LLM",
    }
    
    optional_vars = {
        "API_TOKEN": "Bright Data API token (optional)",
    }
    
    all_set = True
    
    print("Required variables:")
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value and value != f"your_{var.lower()}_here":
            print(f"✅ {var} - {description}")
        else:
            print(f"❌ {var} - {description} (NOT SET)")
            all_set = False
    
    print("\nOptional variables:")
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value and value != f"your_{var.lower()}_here":
            print(f"✅ {var} - {description}")
        else:
            print(f"⚠️  {var} - {description} (not set)")
    
    if not all_set:
        print("\n⚠️  Please edit .env and add required API keys")
        return False
    
    return True

def main():
    """Main setup process"""
    print("\n" + "🚀 "*20)
    print("     AGENTIC CHATBOT BACKEND SETUP")
    print("🚀 "*20)
    
    # Step 1: Check Python
    check_python_version()
    
    # Step 2: Create directories
    create_directories()
    
    # Step 3: Setup .env
    setup_env_file()
    
    # Step 4: Check dependencies
    deps_ok = check_dependencies()
    
    # Step 5: Check credentials
    check_credentials()
    
    # Step 6: Check environment variables
    env_ok = check_env_variables()
    
    # Summary
    print_header("Setup Summary")
    
    if deps_ok and env_ok:
        print("✅ Setup complete! You're ready to start the server.")
        print("\nNext steps:")
        print("1. Generate Google OAuth tokens:")
        print("   python backend/scripts/generate_tokens.py")
        print("\n2. Start the server:")
        print("   python -m backend.api.main")
        print("   or")
        print("   uvicorn backend.api.main:app --reload")
    else:
        print("⚠️  Setup incomplete. Please fix the issues above.")
        if not deps_ok:
            print("\n• Install dependencies: pip install -r requirements.txt")
        if not env_ok:
            print("\n• Edit .env and add your API keys")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()