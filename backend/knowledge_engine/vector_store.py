"""
Supabase Vector Store
Replaces FAISS with Supabase vector storage
"""

import logging
import json
from typing import List, Dict
import numpy as np
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseVectorStore:
    """
    Supabase-based vector store with PostgreSQL pgvector
    """
    
    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        embedding_dim: int = 384
    ):
        """
        Initialize Supabase vector store
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service role key
            embedding_dim: Dimension of embeddings
        """
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.embedding_dim = embedding_dim
        
        logger.info("Initialized Supabase vector store")
    
    def add_documents(
        self,
        embeddings: np.ndarray,
        chunks: List[Dict],
        paper_id: str,
        user_id: str = None
    ) -> Dict:
        """
        Add documents to Supabase
        
        Args:
            embeddings: Matrix of embeddings (n_chunks, embedding_dim)
            chunks: List of chunk dictionaries
            paper_id: ID of the paper these chunks belong to
            user_id: Optional user identifier
            
        Returns:
            Insertion results
        """
        if embeddings.shape[0] != len(chunks):
            raise ValueError("Number of embeddings must match number of chunks")
        
        try:
            # First, insert paper record if it doesn't exist
            paper_data = {
                'id': paper_id,
                'filename': chunks[0]['metadata'].get('filename', 'unknown'),
                'user_id': user_id,
                'processed': True
            }
            
            self.supabase.table('papers').upsert(paper_data).execute()
            
            # Prepare chunk records
            chunk_records = []
            for i, (embedding, chunk) in enumerate(zip(embeddings, chunks)):
                chunk_record = {
                    'paper_id': paper_id,
                    'chunk_text': chunk['text'],
                    'chunk_index': i,
                    'start_char': chunk.get('start_char', 0),
                    'end_char': chunk.get('end_char', 0),
                    'embedding': embedding.tolist(),  # Convert numpy to list
                    'metadata': chunk.get('metadata', {})
                }
                chunk_records.append(chunk_record)
            
            # Batch insert chunks
            if chunk_records:
                response = self.supabase.table('document_chunks').insert(chunk_records).execute()
                
                logger.info(f"Added {len(chunks)} chunks for paper {paper_id}")
                return {
                    'success': True,
                    'chunks_inserted': len(chunks),
                    'paper_id': paper_id
                }
            
        except Exception as e:
            logger.error(f"Error adding documents to Supabase: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        user_id: str = None,
        filter_paper_id: str = None
    ) -> List[Dict]:
        """
        Search for similar chunks using Supabase vector search
        
        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            user_id: Filter by user ID
            filter_paper_id: Filter by specific paper
            
        Returns:
            List of dictionaries with chunk data and scores
        """
        try:
            # Convert embedding to list for Supabase
            embedding_list = query_embedding.tolist()
            
            # Build the query
            query = self.supabase.rpc(
                'match_document_chunks',
                {
                    'query_embedding': embedding_list,
                    'match_count': k,
                    'user_id_filter': user_id,
                    'paper_id_filter': filter_paper_id
                }
            )
            
            response = query.execute()
            
            results = []
            for row in response.data:
                result = {
                    'chunk': {
                        'text': row['chunk_text'],
                        'metadata': row['metadata'] or {}
                    },
                    'score': row['similarity'],
                    'paper_id': row['paper_id']
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching in Supabase: {e}")
            return []
    
    def delete_paper(self, paper_id: str) -> Dict:
        """
        Delete paper and all its chunks from Supabase
        
        Args:
            paper_id: ID of the paper to delete
            
        Returns:
            Deletion results
        """
        try:
            # Delete paper (cascade will delete chunks)
            response = self.supabase.table('papers').delete().eq('id', paper_id).execute()
            
            return {
                'success': True,
                'paper_id': paper_id,
                'message': f'Deleted paper {paper_id}'
            }
            
        except Exception as e:
            logger.error(f"Error deleting paper from Supabase: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_paper_user(self, paper_id: str, user_id: str) -> Dict:
        """Update the user_id for a paper"""
        try:
            response = self.supabase.table('papers').update(
                {'user_id': user_id}
            ).eq('id', paper_id).execute()
            
            return {'success': True, 'paper_id': paper_id}
        except Exception as e:
            logger.error(f"Error updating paper user: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_all_papers(self, user_id: str = None) -> List[Dict]:
        """
        Get all papers for a user
        
        Args:
            user_id: Optional user filter
            
        Returns:
            List of papers
        """
        try:
            query = self.supabase.table('papers').select('*')
            
            if user_id:
                query = query.eq('user_id', user_id)
            
            response = query.execute()
            return response.data
            
        except Exception as e:
            logger.error(f"Error getting papers from Supabase: {e}")
            return []
    
    def get_stats(self, user_id: str = None) -> Dict:
        """Get statistics about stored documents"""
        try:
            # Get paper count
            paper_query = self.supabase.table('papers').select('id', count='exact')
            if user_id:
                paper_query = paper_query.eq('user_id', user_id)
            paper_response = paper_query.execute()
            
            # Get chunk count
            chunk_query = self.supabase.table('document_chunks').select('id', count='exact')
            chunk_response = chunk_query.execute()
            
            return {
                'total_papers': paper_response.count or 0,
                'total_chunks': chunk_response.count or 0,
                'embedding_dim': self.embedding_dim
            }
            
        except Exception as e:
            logger.error(f"Error getting stats from Supabase: {e}")
            return {'error': str(e)}