"""
Club Knowledge Embedding Generation Script

Generates embeddings and creates FAISS index for club knowledge.

Usage:
    python -m knowledge_engine.club.scripts.generate_club_embeddings

Prerequisites:
    1. Run ingestion first: python -m knowledge_engine.club.scripts.ingest_club_knowledge
    2. Ensure embedding_service is configured
"""
import sys
from pathlib import Path

from knowledge_engine.club.embedding_generator import embedding_generator
from knowledge_engine.club.vector_store import club_vector_store
from utils.logger import logger


def main():
    """Run club knowledge embedding generation"""
    print("\n" + "="*80)
    print("ROBOTICS CLUB KNOWLEDGE - EMBEDDING GENERATION")
    print("="*80)
    print()
    
    # Check prerequisites
    print("Checking prerequisites...")
    try:
        from knowledge_engine.club.config import club_config
        
        chunks_file = club_config.CLUB_METADATA_DIR / "chunks_latest.json"
        
        if not chunks_file.exists():
            print(f"❌ ERROR: No chunks file found!")
            print(f"   Expected at: {chunks_file}")
            print()
            print("Please run ingestion first:")
            print("  python -m knowledge_engine.club.scripts.ingest_club_knowledge")
            sys.exit(1)
        
        print(f"✓ Chunks file found: {chunks_file}")
        print(f"✓ Indices directory: {club_config.CLUB_INDICES_DIR}")
        print()
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    
    # Check embedding service
    print("Checking embedding service...")
    try:
        from knowledge_engine.embedding_service import EmbeddingService
        
        # Test with a dummy text
        test_service = EmbeddingService()
        test_embedding = test_service.embed_texts(["test"])
        
        print(f"✓ Embedding service working (dim={test_embedding.shape[1]})")
        print()
        
    except ImportError:
        print("❌ ERROR: embedding_service not found!")
        print()
        print("Please ensure your embedding service is properly configured.")
        print("Expected location: knowledge_engine/embedding_service.py")
        sys.exit(1)
    except Exception as e:
        print(f"⚠️  Warning: {e}")
        print()
    
    # Run embedding generation
    print("Starting embedding generation...")
    print()
    
    try:
        result = embedding_generator.generate_embeddings_from_chunks()
        
        print()
        print("="*80)
        print("EMBEDDING GENERATION RESULTS")
        print("="*80)
        print(f"Status: {result['status'].upper()}")
        print()
        print("Statistics:")
        print(f"  Chunks processed: {result['num_chunks']}")
        print(f"  Embeddings generated: {result['num_embeddings']}")
        print()
        
        if result.get('index_info'):
            index_info = result['index_info']
            print("FAISS Index:")
            print(f"  Vectors: {index_info.get('num_vectors', 0)}")
            print(f"  Path: {index_info.get('index_path', 'N/A')}")
            print()
        
        if result.get('errors'):
            print("Errors:")
            for error in result['errors']:
                print(f"  - {error}")
            print()
        
        if result['status'] == 'success':
            print("✅ Embedding generation completed successfully!")
            print()
            
            # Show index stats
            print("Index Statistics:")
            stats = club_vector_store.get_stats()
            print(f"  Total vectors: {stats.get('total_vectors', 0)}")
            print(f"  Dimension: {stats.get('dimension', 384)}")
            
            if 'category_counts' in stats:
                print(f"  By category:")
                for cat, count in stats['category_counts'].items():
                    print(f"    - {cat}: {count}")
            print()
            
            print("Next steps:")
            print("  1. Test retrieval: python -m knowledge_engine.club.scripts.test_club_retrieval")
            print("  2. Integrate with LangGraph workflow (Step 3)")
        else:
            print("❌ Embedding generation failed")
            print("    Check logs for details")
        
        print("="*80)
        print()
        
        # Exit with appropriate code
        sys.exit(0 if result['status'] == 'success' else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Embedding generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logger.exception("Fatal error during embedding generation")
        sys.exit(1)


if __name__ == "__main__":
    main()