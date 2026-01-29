"""
Configuration management for Ultra Pro Max Bot
"""

import os
from dataclasses import dataclass
from typing import Optional

def get_env_str(name: str, default: str = "") -> str:
    """Get environment variable as string"""
    value = os.getenv(name)
    return str(value).strip() if value is not None else default

def get_env_int(name: str, default: int = 0) -> int:
    """Get environment variable as integer"""
    try:
        value = os.getenv(name)
        return int(str(value).strip()) if value is not None else default
    except (ValueError, TypeError):
        return default

def get_env_bool(name: str, default: bool = False) -> bool:
    """Get environment variable as boolean"""
    value = os.getenv(name, "").lower().strip()
    if value in ("true", "yes", "1", "on", "y"):
        return True
    elif value in ("false", "no", "0", "off", "n"):
        return False
    return default

@dataclass
class BotConfig:
    # Telegram API (Required)
    bot_token: str
    api_id: int
    api_hash: str
    
    # Telegram IDs (Required)
    allowed_group_id: int
    admin_req_channel_id: int
    log_channel_id: int
    
    # Database (Required)
    mongo_uri: str
    tmdb_api_key: str
    
    # Application Settings
    port: int = 10000
    app_name: str = "ultra-pro-max-bot"
    webhook_url: Optional[str] = None
    
    # Database Names
    files_db_name: str = "autofilter"
    files_collection: str = "royal_files"
    bot_db_name: str = "requestbot"
    
    # Limits & Pagination
    max_search_results: int = 10
    max_requests_per_user: int = 3
    request_expire_days: int = 7
    poll_interval: int = 30
    scan_limit: int = 1000
    
    # Features Toggles
    debug_mode: bool = False
    maintenance_mode: bool = False
    enable_auto_notify: bool = True
    enable_request_system: bool = True
    enable_file_search: bool = True
    
    # Performance
    cache_ttl: int = 300
    max_cache_size: int = 1000
    connection_pool_size: int = 10
    
    # File Matching Thresholds
    match_threshold_with_year: float = 0.65
    match_threshold_no_year: float = 0.75
    jaccard_weight: float = 0.6
    sequence_weight: float = 0.4
    
    def validate(self) -> list:
        """Validate configuration and return errors"""
        errors = []
        
        if not self.bot_token or len(self.bot_token) < 10:
            errors.append("Invalid BOT_TOKEN")
        
        if not self.api_id or self.api_id <= 0:
            errors.append("Invalid API_ID")
        
        if not self.api_hash or len(self.api_hash) < 10:
            errors.append("Invalid API_HASH")
        
        if not self.allowed_group_id:
            errors.append("ALLOWED_GROUP_ID is required")
        
        if not self.admin_req_channel_id:
            errors.append("ADMIN_REQ_CHANNEL_ID is required")
        
        if not self.mongo_uri or "mongodb" not in self.mongo_uri:
            errors.append("Invalid MONGO_URI")
        
        if not self.tmdb_api_key or len(self.tmdb_api_key) < 10:
            errors.append("Invalid TMDB_API_KEY")
        
        return errors

# Initialize configuration
CFG = BotConfig(
    # Required - Set in environment variables
    bot_token=get_env_str("BOT_TOKEN"),
    api_id=get_env_int("API_ID"),
    api_hash=get_env_str("API_HASH"),
    allowed_group_id=get_env_int("ALLOWED_GROUP_ID"),
    admin_req_channel_id=get_env_int("ADMIN_REQ_CHANNEL_ID"),
    log_channel_id=get_env_int("LOG_CHANNEL_ID", 0),
    mongo_uri=get_env_str("MONGO_URI"),
    tmdb_api_key=get_env_str("TMDB_API_KEY"),
    
    # Optional with defaults
    port=get_env_int("PORT", 10000),
    app_name=get_env_str("APP_NAME", "ultra-pro-max-bot"),
    webhook_url=get_env_str("WEBHOOK_URL", ""),
    
    # Features
    debug_mode=get_env_bool("DEBUG_MODE", False),
    maintenance_mode=get_env_bool("MAINTENANCE_MODE", False),
    enable_auto_notify=get_env_bool("ENABLE_AUTO_NOTIFY", True),
    enable_request_system=get_env_bool("ENABLE_REQUEST_SYSTEM", True),
    enable_file_search=get_env_bool("ENABLE_FILE_SEARCH", True),
    
    # Performance
    cache_ttl=get_env_int("CACHE_TTL", 300),
    max_cache_size=get_env_int("MAX_CACHE_SIZE", 1000),
    connection_pool_size=get_env_int("CONNECTION_POOL_SIZE", 10),
)

# Export config
__all__ = ['CFG', 'BotConfig', 'get_env_str', 'get_env_int', 'get_env_bool']
