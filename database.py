"""
Database connection and models for Ultra Pro Max Bot
"""

import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError, OperationFailure
from bson import ObjectId

from config import CFG

class Logger:
    """Simple logger for database module"""
    @staticmethod
    def log(msg: str, level: str = "INFO"):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] [DB] {msg}", flush=True)

class MongoDBManager:
    """Managed MongoDB connection with retry logic and connection pooling"""
    
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.connected = False
        self.last_ping = 0
        self.ping_interval = 60  # Ping every 60 seconds
        self.lock = threading.Lock()
        
    def connect(self) -> bool:
        """Establish MongoDB connection with retry logic"""
        with self.lock:
            if self.connected and self.client:
                # Check if connection is still alive
                if time.time() - self.last_ping < self.ping_interval:
                    return True
                try:
                    self.client.admin.command('ping')
                    self.last_ping = time.time()
                    return True
                except:
                    self.connected = False
        
        # Connection parameters for Render compatibility
        connection_params = {
            "connectTimeoutMS": 10000,
            "serverSelectionTimeoutMS": 10000,
            "socketTimeoutMS": 30000,
            "maxPoolSize": CFG.connection_pool_size,
            "minPoolSize": 1,
            "retryWrites": True,
            "retryReads": True,
            "appname": CFG.app_name,
            "heartbeatFrequencyMS": 30000,
            "serverSelectionTryOnce": False
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                Logger.log(f"Connecting to MongoDB (attempt {attempt + 1}/{max_retries})")
                
                # Create client
                self.client = MongoClient(CFG.mongo_uri, **connection_params)
                
                # Test connection
                self.client.admin.command('ping')
                self.last_ping = time.time()
                
                # Initialize collections
                self._init_collections()
                
                self.connected = True
                Logger.log("MongoDB connected successfully")
                return True
                
            except Exception as e:
                Logger.log(f"Connection attempt {attempt + 1} failed: {str(e)[:100]}", "ERROR")
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    Logger.log(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    Logger.log(f"Failed to connect after {max_retries} attempts", "ERROR")
                    self.connected = False
                    return False
        
        return False
    
    def _init_collections(self):
        """Initialize all database collections with indexes"""
        try:
            # Main files collection (from autofilter bot - read-only for us)
            files_db = self.client[CFG.files_db_name]
            files_collection = files_db[CFG.files_collection]
            
            # Bot's own database
            bot_db = self.client[CFG.bot_db_name]
            
            # Users collection
            users_collection = bot_db["users"]
            try:
                users_collection.create_index([("user_id", ASCENDING)], unique=True)
                users_collection.create_index([("last_seen", DESCENDING)])
                users_collection.create_index([("requests_count", DESCENDING)])
                Logger.log("Users collection indexes created")
            except OperationFailure as e:
                Logger.log(f"Could not create users indexes (may be Atlas free tier): {e}", "WARNING")
            
            # Requests collection
            requests_collection = bot_db["requests"]
            try:
                requests_collection.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
                requests_collection.create_index([("media_type", ASCENDING), ("tmdb_id", ASCENDING), ("status", ASCENDING)])
                requests_collection.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
                requests_collection.create_index([("created_at", DESCENDING)])
                requests_collection.create_index([("updated_at", DESCENDING)])
                Logger.log("Requests collection indexes created")
            except OperationFailure as e:
                Logger.log(f"Could not create requests indexes: {e}", "WARNING")
            
            # Metadata collection
            meta_collection = bot_db["meta"]
            try:
                meta_collection.create_index([("key", ASCENDING)], unique=True)
                Logger.log("Meta collection indexes created")
            except OperationFailure as e:
                Logger.log(f"Could not create meta indexes: {e}", "WARNING")
            
            # Cache collection (for TMDB results, etc.)
            cache_collection = bot_db["cache"]
            try:
                cache_collection.create_index([("key", ASCENDING)], unique=True)
                cache_collection.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
                cache_collection.create_index([("created_at", DESCENDING)])
                Logger.log("Cache collection indexes created")
            except OperationFailure as e:
                Logger.log(f"Could not create cache indexes: {e}", "WARNING")
            
            # Statistics collection
            stats_collection = bot_db["stats"]
            try:
                stats_collection.create_index([("date", ASCENDING)], unique=True)
                Logger.log("Stats collection indexes created")
            except OperationFailure as e:
                Logger.log(f"Could not create stats indexes: {e}", "WARNING")
            
            # Store references as module-level variables
            global files_col, users_col, requests_col, meta_col, cache_col, stats_col
            files_col = files_collection
            users_col = users_collection
            requests_col = requests_collection
            meta_col = meta_collection
            cache_col = cache_collection
            stats_col = stats_collection
            
            Logger.log("All collections initialized successfully")
            
        except Exception as e:
            Logger.log(f"Error initializing collections: {e}", "ERROR")
            raise
    
    def disconnect(self):
        """Close MongoDB connection gracefully"""
        with self.lock:
            try:
                if self.client:
                    self.client.close()
                    self.connected = False
                    Logger.log("MongoDB connection closed")
            except Exception as e:
                Logger.log(f"Error disconnecting: {e}", "ERROR")
    
    def ping(self) -> bool:
        """Ping MongoDB to check connection"""
        try:
            if not self.client:
                return False
            
            # Throttle pings
            if time.time() - self.last_ping < self.ping_interval:
                return True
            
            self.client.admin.command('ping')
            self.last_ping = time.time()
            return True
            
        except Exception:
            self.connected = False
            return False
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        try:
            if not self.client:
                return {"status": "disconnected", "client": None}
            
            server_info = self.client.server_info()
            
            return {
                "status": "connected",
                "host": server_info.get("host", "unknown"),
                "version": server_info.get("version", "unknown"),
                "connections": {
                    "current": self.client.max_pool_size,  # Approximate
                    "available": self.client.max_pool_size,
                    "total_created": 0
                },
                "last_ping": datetime.fromtimestamp(self.last_ping).isoformat() if self.last_ping else "never",
                "connected": self.connected
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

# Global database manager instance
db_manager = MongoDBManager()

# Collection references (will be initialized by db_manager)
files_col = None
users_col = None
requests_col = None
meta_col = None
cache_col = None
stats_col = None

def init_database() -> bool:
    """Initialize database connection (called from main app)"""
    return db_manager.connect()

def ping_database() -> bool:
    """Ping database to check connection"""
    return db_manager.ping()

def disconnect_database():
    """Disconnect from database"""
    db_manager.disconnect()

class Cache:
    """MongoDB-based cache implementation"""
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """Get value from cache"""
        try:
            if not ping_database():
                return default
            
            doc = cache_col.find_one({"key": key})
            if not doc:
                return default
            
            # Check expiry
            expires_at = doc.get("expires_at")
            if expires_at and expires_at < datetime.now(timezone.utc):
                cache_col.delete_one({"_id": doc["_id"]})
                return default
            
            return doc.get("value")
            
        except Exception as e:
            Logger.log(f"Cache get error: {e}", "DEBUG")
            return default
    
    @staticmethod
    def set(key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with optional TTL (seconds)"""
        try:
            if not ping_database():
                return
            
            expires_at = None
            if ttl:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
            
            cache_col.update_one(
                {"key": key},
                {
                    "$set": {
                        "value": value,
                        "expires_at": expires_at,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$setOnInsert": {
                        "created_at": datetime.now(timezone.utc)
                    }
                },
                upsert=True
            )
            
        except Exception as e:
            Logger.log(f"Cache set error: {e}", "DEBUG")
    
    @staticmethod
    def delete(key: str):
        """Delete key from cache"""
        try:
            if ping_database():
                cache_col.delete_one({"key": key})
        except Exception:
            pass
    
    @staticmethod
    def clear(pattern: Optional[str] = None):
        """Clear cache (optionally by pattern)"""
        try:
            if not ping_database():
                return
            
            if pattern:
                # Simple pattern matching (starts with)
                query = {"key": {"$regex": f"^{pattern}"}}
            else:
                query = {}
            
            cache_col.delete_many(query)
            
        except Exception as e:
            Logger.log(f"Cache clear error: {e}", "ERROR")

class UserManager:
    """User management operations"""
    
    @staticmethod
    def register_user(user_id: int, username: Optional[str] = None, 
                     first_name: Optional[str] = None, last_name: Optional[str] = None) -> bool:
        """Register or update user in database"""
        try:
            if not ping_database():
                return False
            
            update_data = {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "last_seen": datetime.now(timezone.utc),
                "$inc": {"messages_count": 1}
            }
            
            users_col.update_one(
                {"user_id": user_id},
                {
                    "$set": update_data,
                    "$setOnInsert": {
                        "user_id": user_id,
                        "first_seen": datetime.now(timezone.utc),
                        "requests_count": 0,
                        "messages_count": 1,
                        "is_banned": False,
                        "is_admin": False
                    }
                },
                upsert=True
            )
            
            return True
            
        except Exception as e:
            Logger.log(f"Error registering user {user_id}: {e}", "ERROR")
            return False
    
    @staticmethod
    def get_user(user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        try:
            if ping_database():
                return users_col.find_one({"user_id": user_id})
            return None
        except Exception as e:
            Logger.log(f"Error getting user {user_id}: {e}", "ERROR")
            return None
    
    @staticmethod
    def increment_requests(user_id: int) -> bool:
        """Increment user's request count"""
        try:
            if ping_database():
                users_col.update_one(
                    {"user_id": user_id},
                    {"$inc": {"requests_count": 1}}
                )
                return True
            return False
        except Exception as e:
            Logger.log(f"Error incrementing requests for {user_id}: {e}", "ERROR")
            return False
    
    @staticmethod
    def get_top_users(limit: int = 10) -> List[Dict]:
        """Get top users by request count"""
        try:
            if ping_database():
                return list(users_col.find(
                    {"requests_count": {"$gt": 0}},
                    {"user_id": 1, "username": 1, "first_name": 1, "requests_count": 1}
                ).sort("requests_count", DESCENDING).limit(limit))
            return []
        except Exception as e:
            Logger.log(f"Error getting top users: {e}", "ERROR")
            return []

class RequestManager:
    """Request management operations"""
    
    @staticmethod
    def now() -> datetime:
        """Get current UTC datetime"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def create_request(user_id: int, media_type: str, tmdb_id: int, 
                      title: str, year: Optional[str] = None) -> Optional[str]:
        """Create a new request"""
        try:
            if not ping_database():
                return None
            
            # Check if already exists (pending)
            existing = requests_col.find_one({
                "user_id": user_id,
                "media_type": media_type,
                "tmdb_id": tmdb_id,
                "status": "pending"
            })
            
            if existing:
                return str(existing["_id"])
            
            # Create request document
            request_data = {
                "user_id": user_id,
                "media_type": media_type,
                "tmdb_id": tmdb_id,
                "title": title,
                "year": year,
                "status": "pending",
                "created_at": RequestManager.now(),
                "updated_at": RequestManager.now(),
                "expires_at": RequestManager.now() + timedelta(days=CFG.request_expire_days)
            }
            
            result = requests_col.insert_one(request_data)
            
            # Update user stats
            UserManager.increment_requests(user_id)
            
            # Update daily stats
            today = RequestManager.now().date().isoformat()
            stats_col.update_one(
                {"date": today},
                {"$inc": {"requests_created": 1}},
                upsert=True
            )
            
            return str(result.inserted_id)
            
        except Exception as e:
            Logger.log(f"Error creating request: {e}", "ERROR")
            return None
    
    @staticmethod
    def get_user_requests(user_id: int, status: Optional[str] = "pending", 
                         limit: int = 10) -> List[Dict]:
        """Get user's requests with optional status filter"""
        try:
            if not ping_database():
                return []
            
            query = {"user_id": user_id}
            if status:
                query["status"] = status
            
            return list(requests_col.find(query)
                       .sort("created_at", DESCENDING)
                       .limit(limit))
        except Exception as e:
            Logger.log(f"Error getting user requests: {e}", "ERROR")
            return []
    
    @staticmethod
    def get_pending_requests_count(user_id: int) -> int:
        """Count user's pending requests"""
        try:
            if ping_database():
                return requests_col.count_documents({
                    "user_id": user_id,
                    "status": "pending"
                })
            return 0
        except Exception as e:
            Logger.log(f"Error counting pending requests: {e}", "ERROR")
            return 0
    
    @staticmethod
    def cancel_request(request_id: str, user_id: int) -> bool:
        """Cancel a request (user-initiated)"""
        try:
            if not ping_database():
                return False
            
            result = requests_col.update_one(
                {
                    "_id": ObjectId(request_id),
                    "user_id": user_id,
                    "status": "pending"
                },
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": RequestManager.now(),
                        "updated_at": RequestManager.now()
                    }
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            Logger.log(f"Error cancelling request {request_id}: {e}", "ERROR")
            return False
    
    @staticmethod
    def mark_as_done(media_type: str, tmdb_id: int) -> int:
        """Mark all pending requests for a media as done (filled)"""
        try:
            if not ping_database():
                return 0
            
            result = requests_col.update_many(
                {
                    "media_type": media_type,
                    "tmdb_id": tmdb_id,
                    "status": "pending"
                },
                {
                    "$set": {
                        "status": "done",
                        "done_at": RequestManager.now(),
                        "updated_at": RequestManager.now(),
                        "matched_by": "admin"
                    }
                }
            )
            
            count = result.modified_count
            if count > 0:
                Logger.log(f"Marked {count} requests as done for {media_type} {tmdb_id}")
            
            return count
            
        except Exception as e:
            Logger.log(f"Error marking requests as done: {e}", "ERROR")
            return 0
    
    @staticmethod
    def cancel_by_admin(media_type: str, tmdb_id: int, user_id: int) -> int:
        """Cancel user's requests for a media (admin action)"""
        try:
            if not ping_database():
                return 0
            
            result = requests_col.update_many(
                {
                    "user_id": user_id,
                    "media_type": media_type,
                    "tmdb_id": tmdb_id,
                    "status": "pending"
                },
                {
                    "$set": {
                        "status": "cancelled_by_admin",
                        "cancelled_at": RequestManager.now(),
                        "updated_at": RequestManager.now(),
                        "cancelled_by": "admin"
                    }
                }
            )
            
            return result.modified_count
            
        except Exception as e:
            Logger.log(f"Error cancelling requests by admin: {e}", "ERROR")
            return 0
    
    @staticmethod
    def cleanup_expired() -> int:
        """Clean up expired requests"""
        try:
            if not ping_database():
                return 0
            
            result = requests_col.update_many(
                {
                    "status": "pending",
                    "expires_at": {"$lt": RequestManager.now()}
                },
                {
                    "$set": {
                        "status": "expired",
                        "expired_at": RequestManager.now(),
                        "updated_at": RequestManager.now()
                    }
                }
            )
            
            count = result.modified_count
            if count > 0:
                Logger.log(f"Cleaned up {count} expired requests")
            
            return count
            
        except Exception as e:
            Logger.log(f"Error cleaning up expired requests: {e}", "ERROR")
            return 0

class StatsManager:
    """Statistics management"""
    
    @staticmethod
    def record_search():
        """Record a search in statistics"""
        try:
            if not ping_database():
                return
            
            today = datetime.now(timezone.utc).date().isoformat()
            stats_col.update_one(
                {"date": today},
                {"$inc": {"searches": 1}},
                upsert=True
            )
        except Exception:
            pass
    
    @staticmethod
    def record_result_click():
        """Record a result click in statistics"""
        try:
            if not ping_database():
                return
            
            today = datetime.now(timezone.utc).date().isoformat()
            stats_col.update_one(
                {"date": today},
                {"$inc": {"result_clicks": 1}},
                upsert=True
            )
        except Exception:
            pass
    
    @staticmethod
    def get_daily_stats(date: Optional[str] = None) -> Dict:
        """Get statistics for a specific date (default: today)"""
        try:
            if not ping_database():
                return {}
            
            if not date:
                date = datetime.now(timezone.utc).date().isoformat()
            
            stats = stats_col.find_one({"date": date})
            if stats:
                return stats
            
            return {
                "date": date,
                "searches": 0,
                "result_clicks": 0,
                "requests_created": 0,
                "requests_completed": 0,
                "users_registered": 0
            }
        except Exception as e:
            Logger.log(f"Error getting daily stats: {e}", "ERROR")
            return {}
    
    @staticmethod
    def get_overall_stats() -> Dict:
        """Get overall bot statistics"""
        try:
            if not ping_database():
                return {}
            
            return {
                "total_users": users_col.count_documents({}),
                "total_files": files_col.count_documents({}) if files_col else 0,
                "total_requests": requests_col.count_documents({}),
                "pending_requests": requests_col.count_documents({"status": "pending"}),
                "completed_requests": requests_col.count_documents({"status": "done"}),
                "cancelled_requests": requests_col.count_documents({"status": {"$in": ["cancelled", "cancelled_by_admin"]}})
            }
        except Exception as e:
            Logger.log(f"Error getting overall stats: {e}", "ERROR")
            return {}

# Export public interface
__all__ = [
    'db_manager', 'init_database', 'ping_database', 'disconnect_database',
    'files_col', 'users_col', 'requests_col', 'meta_col', 'cache_col', 'stats_col',
    'Cache', 'UserManager', 'RequestManager', 'StatsManager'
]
