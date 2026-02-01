#!/usr/bin/env python3
"""
Club Knowledge Ingestion Script

Run this to download and process club documents from Google Drive.

Usage:
    python scripts/ingest_club_knowledge.py

Requirements:
    1. CLUB_DRIVE_FOLDER_ID set in .env
    2. Service account JSON at credentials/club_service_account.json
    3. Google Drive folder shared with service account email
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from knowledge_engine.club.ingestion import ingestion
from utils.logger import logger


def main():
    """Run club knowledge ingestion"""
    print("\n" + "="*80)
    print("ROBOTICS CLUB KNOWLEDGE INGESTION")
    print("="*80)
    print()
    
    # Check configuration
    print("Checking configuration...")
    try:
        from knowledge_engine.club.config import club_config
        
        print(f"✓ Root folder ID: {club_config.CLUB_DRIVE_FOLDER_ID[:20]}...")
        print(f"✓ Service account: {club_config.CLUB_DRIVE_SERVICE_ACCOUNT_FILE}")
        print(f"✓ Upload directory: {club_config.CLUB_UPLOADS_DIR}")
        print(f"✓ Metadata directory: {club_config.CLUB_METADATA_DIR}")
        print()
        
        # Check service account file exists
        if not club_config.CLUB_DRIVE_SERVICE_ACCOUNT_FILE.exists():
            print(f"❌ ERROR: Service account file not found!")
            print(f"   Expected at: {club_config.CLUB_DRIVE_SERVICE_ACCOUNT_FILE}")
            print(f"   Please add your Google service account JSON file.")
            sys.exit(1)
        
        print("✓ Configuration valid")
        print()
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    
    # Run ingestion
    print("Starting ingestion pipeline...")
    print()
    
    try:
        result = ingestion.run_full_ingestion()
        
        print()
        print("="*80)
        print("INGESTION RESULTS")
        print("="*80)
        print(f"Status: {result['status'].upper()}")
        print()
        print("Statistics:")
        print(f"  Total files found: {result['stats']['total_files']}")
        print(f"  Files downloaded: {result['stats']['downloaded']}")
        print(f"  Files parsed: {result['stats']['parsed']}")
        print(f"  Total chunks created: {result['stats']['total_chunks']}")
        print()
        
        if result.get('chunks_file'):
            print(f"Chunks saved to: {result['chunks_file']}")
            print(f"Metadata saved to: {result['metadata_file']}")
            print()
        
        if result.get('errors'):
            print("Errors:")
            for error in result['errors']:
                print(f"  - {error}")
            print()
        
        if result['status'] == 'success':
            print("✅ Ingestion completed successfully!")
            print()
            print("Next steps:")
            print("  1. Run embedding generation: python scripts/generate_club_embeddings.py")
            print("  2. Test retrieval: python scripts/test_club_retrieval.py")
        elif result['status'] == 'partial':
            print("⚠️  Ingestion completed with some errors")
            print("    Check logs for details")
        else:
            print("❌ Ingestion failed")
            print("    Check logs for details")
        
        print("="*80)
        print()
        
        # Exit with appropriate code
        sys.exit(0 if result['status'] == 'success' else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Ingestion interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logger.exception("Fatal error during ingestion")
        sys.exit(1)


if __name__ == "__main__":
    main()