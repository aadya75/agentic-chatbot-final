"""
Configuration for Club Knowledge System
Extends existing config with club-specific settings
"""
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClubKnowledgeConfig(BaseSettings):
    """Club Knowledge specific configuration"""
    
    # Embedding model (must match your embedding_service)
    CLUB_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Retrieval settings
    CLUB_TOP_K_RESULTS: int = 5  # Default number of results

    # Chunking (from Step 1)
    CLUB_CHUNK_SIZE: int = 512
    CLUB_CHUNK_OVERLAP: int = 50
    
    # Google Drive Configuration
    CLUB_DRIVE_SERVICE_ACCOUNT_FILE: Path = Field(
        default=Path("credentials/club_service_account.json"),
        description="Service account JSON for club Google Drive"
    )
    CLUB_DRIVE_FOLDER_ID: str = Field(
        ...,
        description="Root RoboticsClub/ folder ID in Google Drive"
    )
    
    # Folder Structure (relative to root)
    CLUB_EVENTS_FOLDER: str = "Events"
    CLUB_ANNOUNCEMENTS_FOLDER: str = "Announcements"
    CLUB_COORDINATORS_FOLDER: str = "Coordinators"
    CLUB_ARCHIVES_FOLDER: str = "Archives"
    
    # Ignored patterns
    CLUB_IGNORED_FILES: list[str] = Field(
        default=["README.md", "readme.md", ".DS_Store"],
        description="Files to ignore during ingestion"
    )
    CLUB_IGNORED_FOLDERS: list[str] = Field(
        default=["Archives"],
        description="Folders to ignore during ingestion"
    )
    
    # Data Storage Paths
    CLUB_DATA_DIR: Path = Field(
        default=Path("data/club_knowledge"),
        description="Directory for club knowledge data"
    )
    CLUB_UPLOADS_DIR: Path = Field(
        default=Path("data/club_knowledge/uploads"),
        description="Downloaded files from Google Drive"
    )
    CLUB_INDICES_DIR: Path = Field(
        default=Path("data/club_knowledge/indices"),
        description="FAISS indices for club knowledge"
    )
    CLUB_METADATA_DIR: Path = Field(
        default=Path("data/club_knowledge/metadata"),
        description="Metadata JSON files"
    )
    
    # Vector Store Configuration
    CLUB_COLLECTION_NAME: str = "robotics_club_knowledge"
    CLUB_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # 384-dim to match your existing system
    CLUB_CHUNK_SIZE: int = 512
    CLUB_CHUNK_OVERLAP: int = 50
    CLUB_TOP_K_RESULTS: int = 5
    
    # Metadata file
    CLUB_LAST_UPDATED_FILE: Path = Field(
        default=Path("data/club_knowledge/last_updated.txt"),
        description="Timestamp of last refresh"
    )
    CLUB_INDEX_METADATA_FILE: Path = Field(
        default=Path("data/club_knowledge/metadata/index_metadata.json"),
        description="Index metadata including document mappings"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create directories
        self.CLUB_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.CLUB_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.CLUB_INDICES_DIR.mkdir(parents=True, exist_ok=True)
        self.CLUB_METADATA_DIR.mkdir(parents=True, exist_ok=True)


# Singleton instance
club_config = ClubKnowledgeConfig()