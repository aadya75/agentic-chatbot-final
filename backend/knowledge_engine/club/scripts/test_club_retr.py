#!/usr/bin/env python3
"""
Test Club Knowledge Retrieval

Tests the club knowledge retrieval system with sample queries.

Usage:
    python scripts/test_club_retrieval.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from knowledge_engine.club.retrieval import club_retriever
from utils.logger import logger


def test_retrieval():
    """Test club knowledge retrieval with sample queries"""
    
    print("\n" + "="*80)
    print("CLUB KNOWLEDGE RETRIEVAL - TEST")
    print("="*80)
    print()
    
    # Check if system is ready
    print("Checking system status...")
    status = club_retriever.check_ready()
    
    print(f"Ready: {status['ready']}")
    print(f"Index loaded: {status['index_loaded']}")
    print(f"Embedding service: {status['embedding_service_available']}")
    
    if status.get('stats'):
        stats = status['stats']
        print(f"\nIndex Statistics:")
        print(f"  Total vectors: {stats.get('total_vectors', 0)}")
        print(f"  Dimension: {stats.get('dimension', 384)}")
        
        if 'category_counts' in stats:
            print(f"  By category:")
            for cat, count in stats['category_counts'].items():
                print(f"    - {cat}: {count}")
    
    print()
    
    if not status['ready']:
        print("❌ System not ready!")
        if not status['index_loaded']:
            print("   Run: python scripts/generate_club_embeddings.py")
        if not status['embedding_service_available']:
            print("   Configure embedding_service")
        sys.exit(1)
    
    print("✅ System ready!")
    print()
    
    # Test queries
    test_queries = [
        {
            "query": "What are the ongoing events?",
            "category": "events",
            "description": "Query about ongoing events"
        },
        {
            "query": "Who is the coordinator for RoboSprint?",
            "category": "coordinators",
            "description": "Query about event coordinator"
        },
        {
            "query": "What are the latest announcements?",
            "category": "announcements",
            "description": "Query about announcements"
        },
        {
            "query": "Tell me about the problem statement for autonomous robots",
            "category": "events",
            "description": "Query about problem statements"
        }
    ]
    
    print("="*80)
    print("RUNNING TEST QUERIES")
    print("="*80)
    print()
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n{'─'*80}")
        print(f"Test {i}: {test['description']}")
        print(f"{'─'*80}")
        print(f"Query: \"{test['query']}\"")
        print(f"Category filter: {test['category']}")
        print()
        
        try:
            results = club_retriever.retrieve(
                query=test['query'],
                category=test['category'],
                top_k=3
            )
            
            print(f"Results: {len(results)} found")
            print()
            
            if not results:
                print("  ⚠️  No results found")
            else:
                for j, result in enumerate(results, 1):
                    print(f"  Result {j}:")
                    print(f"    Score: {result['score']:.4f}")
                    print(f"    Source: {result['metadata'].get('source', 'unknown')}")
                    print(f"    Category: {result['metadata'].get('category', 'unknown')}")
                    
                    if 'event_name' in result['metadata']:
                        print(f"    Event: {result['metadata']['event_name']}")
                    
                    # Show first 150 chars of content
                    content_preview = result['content'][:150].replace('\n', ' ')
                    if len(result['content']) > 150:
                        content_preview += "..."
                    print(f"    Content: {content_preview}")
                    print()
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            logger.exception(e)
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print()
    
    # Show last updated
    last_updated = club_retriever.get_last_updated()
    print(f"📅 Knowledge last updated: {last_updated}")
    print()


def interactive_mode():
    """Interactive query mode"""
    print("\n" + "="*80)
    print("INTERACTIVE QUERY MODE")
    print("="*80)
    print()
    print("Type your queries (or 'quit' to exit)")
    print()
    
    while True:
        try:
            query = input("\n🔍 Query: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye!")
                break
            
            # Ask for category filter
            print("Category filter? (events/announcements/coordinators/none)")
            category_input = input("Category [none]: ").strip().lower()
            
            category = None
            if category_input in ['events', 'announcements', 'coordinators']:
                category = category_input
            
            print()
            print(f"Searching for: \"{query}\"")
            if category:
                print(f"Category: {category}")
            print()
            
            results = club_retriever.retrieve(query, category=category, top_k=5)
            
            if not results:
                print("⚠️  No results found")
            else:
                print(f"Found {len(results)} results:\n")
                
                for i, result in enumerate(results, 1):
                    print(f"{i}. {result['metadata'].get('source', 'unknown')}")
                    print(f"   Score: {result['score']:.4f}")
                    print(f"   {result['content'][:200]}...")
                    print()
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_mode()
    else:
        test_retrieval()


if __name__ == "__main__":
    main()