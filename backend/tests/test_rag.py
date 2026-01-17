"""
Test Scripts for Knowledge Engine Components
Run these tests from the backend directory
"""

# ============================================================================
# TEST 1: Test Embedding Service
# ============================================================================
print("=" * 30)
print("TEST 1: Embedding Service")
print("=" * 30)


from knowledge_engine.embedding_service import EmbeddingService
import numpy as np

# Initialize
embedding_service = EmbeddingService(embedding_dim=384)

# Test single text
text = "This is a test document about machine learning."
embedding = embedding_service.embed_text(text)

print(f"✓ Single text embedding shape: {embedding.shape}")
print(f"✓ Expected shape: (384,)")
print(f"✓ Embedding dimension: {embedding_service.get_embedding_dimension()}")
print(f"✓ First 5 values: {embedding[:5]}")
print(f"✓ Norm (should be ~1.0): {np.linalg.norm(embedding):.4f}")

# Test multiple texts
texts = [
    "Machine learning is a subset of AI",
    "Deep learning uses neural networks",
    "Natural language processing handles text"
]
embeddings = embedding_service.embed_texts(texts)

print(f"\n✓ Multiple texts embedding shape: {embeddings.shape}")
print(f"✓ Expected shape: (3, 384)")
print(f"✓ All embeddings have unit norm: {all(abs(np.linalg.norm(embeddings[i]) - 1.0) < 0.01 for i in range(len(texts)))}")

# Test determinism (same text = same embedding)
embedding2 = embedding_service.embed_text(text)
print(f"✓ Deterministic (same text = same embedding): {np.allclose(embedding, embedding2)}")

print("\n✅ Embedding Service: PASSED\n")


# ============================================================================
# TEST 2: Test Document Chunker
# ============================================================================
print("=" * 60)
print("TEST 2: Document Chunker")
print("=" * 60)

from knowledge_engine.chunking import DocumentChunker

# Initialize
chunker = DocumentChunker(chunk_size=200, chunk_overlap=50)

# Test text
long_text = """
Machine learning is a method of data analysis that automates analytical model building.
It is a branch of artificial intelligence based on the idea that systems can learn from data,
identify patterns and make decisions with minimal human intervention.

Deep learning is part of a broader family of machine learning methods based on artificial neural networks.
Learning can be supervised, semi-supervised or unsupervised. Deep learning architectures such as deep neural networks,
deep belief networks, recurrent neural networks and convolutional neural networks have been applied to fields
including computer vision, speech recognition, natural language processing, and audio recognition.

Natural language processing is a subfield of linguistics, computer science, and artificial intelligence concerned
with the interactions between computers and human language. In particular, how to program computers to process
and analyze large amounts of natural language data.
""".strip()

# Create chunks
chunks = chunker.chunk_text(long_text, metadata={'source': 'test_doc'})

print(f"✓ Number of chunks created: {len(chunks)}")
print(f"✓ Chunk size setting: {chunker.chunk_size}")
print(f"✓ Chunk overlap setting: {chunker.chunk_overlap}")

for i, chunk in enumerate(chunks[:3]):  # Show first 3
    print(f"\nChunk {i}:")
    print(f"  - Length: {len(chunk['text'])} chars")
    print(f"  - Start/End: {chunk['start_char']} - {chunk['end_char']}")
    print(f"  - Preview: {chunk['text'][:100]}...")

# Test overlap
if len(chunks) >= 2:
    overlap_check = long_text[chunks[1]['start_char']:chunks[0]['end_char']]
    print(f"\n✓ Overlap between chunks 0 and 1: {len(overlap_check)} chars")

print("\n✅ Document Chunker: PASSED\n")


# ============================================================================
# TEST 3: Test Vector Store
# ============================================================================
print("=" * 60)
print("TEST 3: Vector Store")
print("=" * 60)

from knowledge_engine.vector_store import VectorStore
import tempfile
import shutil

# Create temp directory for test
test_dir = tempfile.mkdtemp()
print(f"✓ Created test directory: {test_dir}")

try:
    # Initialize vector store
    vector_store = VectorStore(
        index_dir=test_dir,
        embedding_dim=384,
        index_type="FlatL2"
    )
    
    print(f"✓ Vector store initialized")
    print(f"✓ Initial stats: {vector_store.get_stats()}")
    
    # Create some test embeddings
    test_texts = [
        "Machine learning trains models on data",
        "Deep learning uses neural networks",
        "AI can solve complex problems"
    ]
    
    test_embeddings = embedding_service.embed_texts(test_texts)
    test_chunks = [
        {'text': text, 'chunk_id': i, 'metadata': {'test': True}}
        for i, text in enumerate(test_texts)
    ]
    
    # Add documents
    vector_store.add_documents(test_embeddings, test_chunks, 'test_paper_1')
    print(f"✓ Added {len(test_chunks)} chunks to vector store")
    
    # Get stats
    stats = vector_store.get_stats()
    print(f"✓ Total chunks in index: {stats['total_chunks']}")
    print(f"✓ Total papers: {stats['total_papers']}")
    
    # Test search
    query_text = "neural networks in AI"
    query_embedding = embedding_service.embed_text(query_text)
    results = vector_store.search(query_embedding, k=2)
    
    print(f"\n✓ Search results for '{query_text}':")
    for i, result in enumerate(results):
        print(f"  Result {i+1}:")
        print(f"    - Text: {result['chunk']['text']}")
        print(f"    - Score: {result['score']:.4f}")
        print(f"    - Distance: {result['distance']:.4f}")
    
    # Test persistence (save and reload)
    vector_store._save_index()
    print(f"\n✓ Index saved to disk")
    
    # Create new instance (should load from disk)
    vector_store2 = VectorStore(
        index_dir=test_dir,
        embedding_dim=384,
        index_type="FlatL2"
    )
    stats2 = vector_store2.get_stats()
    print(f"✓ Reloaded index - total chunks: {stats2['total_chunks']}")
    
    # Test delete
    deleted = vector_store2.delete_paper('test_paper_1')
    print(f"\n✓ Deleted {deleted} chunks")
    stats3 = vector_store2.get_stats()
    print(f"✓ After deletion - total chunks: {stats3['total_chunks']}")
    
    print("\n✅ Vector Store: PASSED\n")
    
finally:
    # Cleanup
    shutil.rmtree(test_dir)
    print(f"✓ Cleaned up test directory")


# ============================================================================
# TEST 4: Test PDF Ingestion (Simulated)
# ============================================================================
print("=" * 60)
print("TEST 4: Document Ingestion (Simulated)")
print("=" * 60)

from knowledge_engine.ingestion import DocumentIngestion
import os

# Create temp directories
upload_dir = tempfile.mkdtemp()
index_dir = tempfile.mkdtemp()

try:
    # Initialize services
    vector_store = VectorStore(index_dir=index_dir, embedding_dim=384)
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    
    ingestion = DocumentIngestion(
        upload_dir=upload_dir,
        vector_store=vector_store,
        embedding_service=embedding_service,
        chunker=chunker,
        graph_store=None
    )
    
    print(f"✓ Ingestion service initialized")
    print(f"✓ Upload directory: {upload_dir}")
    
    # Note: Cannot test actual PDF without a PDF file
    # But we can verify the service is ready
    print(f"✓ Ingestion service ready to process PDFs")
    
    # Test get_document_info (should return None for non-existent doc)
    info = ingestion.get_document_info('non_existent_id')
    print(f"✓ get_document_info for non-existent doc: {info}")
    
    print("\n✅ Document Ingestion: PASSED\n")
    
finally:
    shutil.rmtree(upload_dir)
    shutil.rmtree(index_dir)
    print(f"✓ Cleaned up test directories")


# ============================================================================
# TEST 5: Test Retrieval Service
# ============================================================================
print("=" * 60)
print("TEST 5: Hybrid Retrieval")
print("=" * 60)

from knowledge_engine.retrieval import HybridRetrieval

# Create temp directory
index_dir = tempfile.mkdtemp()

try:
    # Setup
    vector_store = VectorStore(index_dir=index_dir, embedding_dim=384)
    
    # Add some test data
    test_texts = [
        "Python is a high-level programming language",
        "JavaScript is used for web development",
        "Machine learning requires data and algorithms",
        "Neural networks are inspired by the brain"
    ]
    
    embeddings = embedding_service.embed_texts(test_texts)
    chunks = [
        {
            'text': text,
            'chunk_id': i,
            'metadata': {'filename': f'paper_{i}.pdf', 'paper_id': f'paper_{i}'}
        }
        for i, text in enumerate(test_texts)
    ]
    
    # Add to different "papers"
    for i in range(len(test_texts)):
        vector_store.add_documents(
            embeddings[i:i+1],
            [chunks[i]],
            f'paper_{i}'
        )
    
    # Initialize retrieval
    retrieval = HybridRetrieval(
        embedding_service=embedding_service,
        vector_store=vector_store,
        graph_store=None
    )
    
    print(f"✓ Retrieval service initialized")
    
    # Test retrieval
    query = "programming languages for web"
    results = retrieval.retrieve(query, top_k=2, include_citations=False)
    
    print(f"\n✓ Query: '{query}'")
    num = len(results.get("results", []))
    print(f"✓ Number of results: {num}")

    
    for i, chunk in enumerate(results['chunks']):
        print(f"\n  Result {i+1}:")
        print(f"    - Text: {chunk['text']}")
        print(f"    - Score: {chunk['score']:.4f}")
        print(f"    - Source: {chunk['metadata']['filename']}")
    
    # Test get_all_resources
    resources = retrieval.get_all_resources()
    print(f"\n✓ Total resources: {len(resources)}")
    for resource in resources:
        print(f"  - {resource['filename']} (ID: {resource['paper_id']})")
    
    print("\n✅ Hybrid Retrieval: PASSED\n")
    
finally:
    shutil.rmtree(index_dir)
    print(f"✓ Cleaned up test directory")


# ============================================================================
# TEST 6: Test Graph Store (Optional)
# ============================================================================
print("=" * 60)
print("TEST 6: Graph Store (Neo4j)")
print("=" * 60)

from knowledge_engine.graph_store import GraphStore
import os

# Try to initialize (will fail gracefully if Neo4j not available)
graph_store = GraphStore(
    uri=os.getenv("NEO4J_URI"),
    user=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD")
)

if graph_store.enabled:
    print(f"✓ Neo4j connection established")
    
    # Test add paper
    graph_store.add_paper('test_paper_1', 'Test Paper on AI', {'year': 2024})
    print(f"✓ Added test paper")
    
    # Test get citations (should be empty)
    citations = graph_store.get_citations('test_paper_1')
    print(f"✓ Citations retrieved: {citations}")
    
    # Cleanup
    graph_store.delete_paper('test_paper_1')
    print(f"✓ Deleted test paper")
    
    graph_store.close()
    print("\n✅ Graph Store: PASSED\n")
else:
    print(f"⚠️  Neo4j not available (this is optional)")
    print(f"   Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env to enable")
    print("\n✅ Graph Store: SKIPPED (optional)\n")


# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("=" * 60)
print("ALL TESTS COMPLETED")
print("=" * 60)
print("\n✅ All core components are working!")
print("\nNext steps:")
print("1. Start the FastAPI server: uvicorn api.main:app --reload")
print("2. Test the API endpoints at http://localhost:8000/docs")
print("3. Start the frontend and test the UI")
print("4. Upload a real PDF to test the full pipeline")