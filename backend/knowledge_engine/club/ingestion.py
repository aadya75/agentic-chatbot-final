"""
Club Knowledge Ingestion Orchestrator
Downloads, parses, chunks, and prepares documents for embedding
"""
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from knowledge_engine.club.config import club_config
from knowledge_engine.club.drive_client import drive_client
from knowledge_engine.club.parser import parser
from knowledge_engine.club.chunker import chunker
from utils.logger import logger


class ClubKnowledgeIngestion:
    """
    Orchestrates the complete ingestion pipeline:
    1. Download documents from Google Drive
    2. Parse documents
    3. Chunk documents
    4. Prepare for embedding
    5. Save metadata
    """
    
    def __init__(self):
        self.drive_client = drive_client
        self.parser = parser
        self.chunker = chunker
        
        logger.info("ClubKnowledgeIngestion initialized")
    
    def run_full_ingestion(self) -> Dict[str, Any]:
        """
        Run the complete ingestion pipeline
        
        Returns:
            {
                "status": "success" | "partial" | "failed",
                "timestamp": str,
                "stats": {
                    "total_files": int,
                    "downloaded": int,
                    "parsed": int,
                    "total_chunks": int
                },
                "chunks_file": str,  # Path to saved chunks JSON
                "metadata_file": str  # Path to saved metadata JSON
            }
        """
        logger.info("="*80)
        logger.info("STARTING CLUB KNOWLEDGE INGESTION")
        logger.info("="*80)
        
        result = {
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "stats": {
                "total_files": 0,
                "downloaded": 0,
                "parsed": 0,
                "total_chunks": 0
            },
            "chunks_file": None,
            "metadata_file": None,
            "errors": []
        }
        
        try:
            # Step 1: Download documents
            logger.info("Step 1: Downloading documents from Google Drive...")
            download_result = self.drive_client.download_all_documents()
            
            result["stats"]["total_files"] = download_result["total_files"]
            result["stats"]["downloaded"] = download_result["downloaded"]
            
            if download_result["downloaded"] == 0:
                logger.warning("No documents downloaded!")
                result["status"] = "failed"
                result["errors"].append("No documents downloaded from Google Drive")
                return result
            
            logger.info(f"✓ Downloaded {download_result['downloaded']} files")
            
            # Step 2: Parse documents
            logger.info("Step 2: Parsing documents...")
            parsed_docs = self._parse_documents(download_result["files"])
            
            result["stats"]["parsed"] = len(parsed_docs)
            
            if len(parsed_docs) == 0:
                logger.warning("No documents parsed!")
                result["status"] = "failed"
                result["errors"].append("No documents successfully parsed")
                return result
            
            logger.info(f"✓ Parsed {len(parsed_docs)} documents")
            
            # Step 3: Chunk documents
            logger.info("Step 3: Chunking documents...")
            chunks = self.chunker.chunk_multiple_documents(parsed_docs)
            
            result["stats"]["total_chunks"] = len(chunks)
            
            if len(chunks) == 0:
                logger.warning("No chunks created!")
                result["status"] = "failed"
                result["errors"].append("No chunks created from documents")
                return result
            
            logger.info(f"✓ Created {len(chunks)} chunks")
            
            # Step 4: Save chunks and metadata
            logger.info("Step 4: Saving chunks and metadata...")
            chunks_file, metadata_file = self._save_chunks_and_metadata(chunks, download_result)
            
            result["chunks_file"] = str(chunks_file)
            result["metadata_file"] = str(metadata_file)
            
            logger.info(f"✓ Saved chunks to: {chunks_file}")
            logger.info(f"✓ Saved metadata to: {metadata_file}")
            
            # Step 5: Update last_updated timestamp
            self._update_timestamp()
            
            # Determine final status
            if download_result["errors"] > 0:
                result["status"] = "partial"
                result["errors"].append(f"{download_result['errors']} files had errors during download")
            else:
                result["status"] = "success"
            
            logger.info("="*80)
            logger.info(f"INGESTION COMPLETE: {result['status'].upper()}")
            logger.info(f"Files: {result['stats']['downloaded']}/{result['stats']['total_files']}")
            logger.info(f"Chunks: {result['stats']['total_chunks']}")
            logger.info("="*80)
            
            return result
            
        except Exception as e:
            logger.error(f"Fatal error during ingestion: {e}")
            result["status"] = "failed"
            result["errors"].append(str(e))
            return result
    
    def _parse_documents(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse all downloaded files"""
        parsed_docs = []
        
        for file_info in files:
            local_path = Path(file_info["local_path"])
            metadata = file_info["metadata"]
            
            try:
                parsed = self.parser.parse_file(local_path, metadata)
                
                if parsed:
                    parsed_docs.append(parsed)
                else:
                    logger.warning(f"Failed to parse: {file_info['path']}")
                    
            except Exception as e:
                logger.error(f"Error parsing {file_info['path']}: {e}")
                continue
        
        return parsed_docs
    
    def _save_chunks_and_metadata(
        self,
        chunks: List[Dict[str, Any]],
        download_result: Dict[str, Any]
    ) -> tuple[Path, Path]:
        """
        Save chunks and metadata to JSON files
        
        This prepares data for the embedding step (which will be separate)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save chunks
        chunks_file = club_config.CLUB_METADATA_DIR / f"chunks_{timestamp}.json"
        with open(chunks_file, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        
        # Save ingestion metadata
        metadata = {
            "ingestion_timestamp": download_result["timestamp"],
            "total_files": download_result["total_files"],
            "downloaded_files": download_result["downloaded"],
            "skipped_files": download_result["skipped"],
            "error_count": download_result["errors"],
            "total_chunks": len(chunks),
            "files": download_result["files"],
            "chunk_size": self.chunker.chunk_size,
            "chunk_overlap": self.chunker.chunk_overlap
        }
        
        metadata_file = club_config.CLUB_METADATA_DIR / f"ingestion_metadata_{timestamp}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Also save as "latest" for easy access
        latest_chunks = club_config.CLUB_METADATA_DIR / "chunks_latest.json"
        latest_metadata = club_config.CLUB_METADATA_DIR / "ingestion_metadata_latest.json"
        
        with open(latest_chunks, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        
        with open(latest_metadata, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return chunks_file, metadata_file
    
    def _update_timestamp(self):
        """Update last_updated.txt"""
        timestamp = datetime.now().isoformat()
        club_config.CLUB_LAST_UPDATED_FILE.write_text(timestamp)
        logger.info(f"Updated timestamp: {timestamp}")
    
    def get_last_updated(self) -> str:
        """Get last ingestion timestamp"""
        if club_config.CLUB_LAST_UPDATED_FILE.exists():
            return club_config.CLUB_LAST_UPDATED_FILE.read_text().strip()
        return "Never"
    
    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get statistics from last ingestion"""
        latest_metadata = club_config.CLUB_METADATA_DIR / "ingestion_metadata_latest.json"
        
        if not latest_metadata.exists():
            return {
                "status": "no_ingestion",
                "last_updated": "Never"
            }
        
        try:
            with open(latest_metadata, 'r') as f:
                metadata = json.load(f)
            
            return {
                "status": "completed",
                "last_updated": self.get_last_updated(),
                "total_files": metadata.get("total_files", 0),
                "downloaded_files": metadata.get("downloaded_files", 0),
                "total_chunks": metadata.get("total_chunks", 0),
                "error_count": metadata.get("error_count", 0)
            }
            
        except Exception as e:
            logger.error(f"Error reading ingestion stats: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Singleton
ingestion = ClubKnowledgeIngestion()