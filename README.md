# Agentic Chatbot

An intelligent chatbot powered by LangChain, FastMCP, and React.

## Features

- 🤖 Multi-tool agent with LangChain
- 📧 Gmail integration
- 📁 Google Drive integration
- 📅 Google Calendar integration
- 🧮 Math calculations
- 🔍 Web search 

## Quick Start

### Backend Setup
\`\`\`bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python scripts/generate_tokens.py  # For Google OAuth
uvicorn api.main:app --reload
\`\`\`

### Frontend Setup
\`\`\`bash
cd frontend
npm install
cp .env.example .env
npm run dev
\`\`\`

Visit http://localhost:3000