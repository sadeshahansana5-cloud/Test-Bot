"""
Main application file for Ultra Pro Max Bot
Combines all modules and runs the bot
"""

import asyncio
import signal
import sys
import threading
import time
from datetime import datetime, timezone

from flask import Flask
from pyrogram import Client

from config import CFG
from database import init_database, ping_database, disconnect_database, RequestManager
from tmdb import tmdb_client
from matcher import matcher
from handlers.group import setup_group_handlers
from handlers.private import setup_private_handlers
from handlers.callbacks import setup_callback_handlers

# Global bot instance
bot = None
app_start_time = time.time()

# Flask web server for health checks
web = Flask(__name__)

@web.route('/')
def home():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Ultra Pro Max Bot",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": get_uptime()
    }

@web.route('/health')
def health():
    """Detailed health check"""
    try:
        mongo_status = "healthy" if ping_database() else "unhealthy"
        
        # Check TMDB
        tmdb_status = "unknown"
        try:
            # Try a simple configuration request
            import requests
            response = requests.get(
                "https://api.themoviedb.org/3/configuration",
                params={"api_key": CFG.tmdb_api_key},
                timeout=5
            )
            tmdb_status = "healthy" if response.status_code == 200 else "unhealthy"
        except:
            tmdb_status = "unhealthy"
        
        # Check bot status
        bot_status = "connected" if bot and bot.is_connected else "disconnected"
        
        return {
            "status": "healthy",
            "checks": {
                "mongodb": mongo_status,
                "tmdb": tmdb_status,
                "bot": bot_status
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 500

@web.route('/stats')
def stats():
    """Get bot statistics"""
    try:
        from database import users_col, files_col, requests_col
        
        stats_data = {
            "users_count": users_col.count_documents({}) if users_col else 0,
            "files_count": files_col.count_documents({}) if files_col else 0,
            "pending_requests": requests_col.count_documents({"status": "pending"}) if requests_col else 0,
            "total_requests": requests_col.count_documents({}) if requests_col else 0,
            "completed_requests": requests_col.count_documents({"status": "done"}) if requests_col else 0,
            "uptime": get_uptime(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        return stats_data
    except Exception as e:
        return {"error": str(e)}, 500

def run_flask():
    """Run Flask web server"""
    web.run(host="0.0.0.0", port=CFG.port, debug=False, threaded=True, use_reloader=False)

def get_uptime() -> str:
    """Get formatted uptime"""
    seconds = int(time.time() - app_start_time)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

class UltraProMaxBot:
    """Main bot class"""
    
    def __init__(self):
        self.bot = None
        self.running = False
        
    async def start(self):
        """Start the bot"""
        print("=" * 50)
        print("Ultra Pro Max Bot Starting...")
        print("=" * 50)
        
        # Validate configuration
        config_errors = CFG.validate()
        if config_errors:
            print("❌ Configuration errors:")
            for error in config_errors:
                print(f"  - {error}")
            print("Please check your environment variables and restart.")
            return
        
        # Print configuration
        masked_mongo = CFG.mongo_uri
        if "@" in masked_mongo:
            parts = masked_mongo.split("@")
            masked_mongo = f"mongodb://****:****@{parts[1]}"
        
        print(f"Bot: @{CFG.bot_token.split(':')[0]}")
        print(f"Group ID: {CFG.allowed_group_id}")
        print(f"Admin Channel: {CFG.admin_req_channel_id}")
        print(f"MongoDB: {masked_mongo}")
        print(f"Debug Mode: {CFG.debug_mode}")
        print(f"Features - Search: {CFG.enable_file_search}, "
              f"Requests: {CFG.enable_request_system}, "
              f"Auto-notify: {CFG.enable_auto_notify}")
        print("=" * 50)
        
        # Initialize MongoDB
        print("Connecting to MongoDB...")
        if not init_database():
            print("❌ Failed to connect to MongoDB. Exiting.")
            return
        
        # Start Flask web server in background thread
        print(f"Starting web server on port {CFG.port}...")
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Initialize bot client
        self.bot = Client(
            name=CFG.app_name,
            api_id=CFG.api_id,
            api_hash=CFG.api_hash,
            bot_token=CFG.bot_token,
            workers=10,
            sleep_threshold=30,
            parse_mode="HTML"
        )
        
        # Setup handlers
        print("Setting up handlers...")
        setup_group_handlers(self.bot)
        setup_private_handlers(self.bot)
        setup_callback_handlers(self.bot)
        
        # Start bot
        print("Starting bot...")
        await self.bot.start()
        
        # Get bot info
        me = await self.bot.get_me()
        print(f"Bot started: @{me.username}")
        
        # Send startup notification to admin channel
        if CFG.admin_req_channel_id:
            try:
                startup_msg = (
                    f"🤖 <b>Bot Started Successfully</b>\n\n"
                    f"• <b>Name:</b> @{me.username}\n"
                    f"• <b>Time:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                    f"• <b>Uptime:</b> {get_uptime()}\n"
                    f"• <b>Version:</b> 2.0.0\n\n"
                    f"✅ All systems operational."
                )
                
                await self.bot.send_message(CFG.admin_req_channel_id, startup_msg)
            except Exception as e:
                print(f"Failed to send startup notification: {e}")
        
        # Bot is ready
        print("=" * 50)
        print("Bot is ready and running!")
        print(f"Group: {CFG.allowed_group_id}")
        print(f"Admin Channel: {CFG.admin_req_channel_id}")
        print("=" * 50)
        
        self.running = True
        
        # Keep bot running
        await self.idle()
    
    async def idle(self):
        """Keep bot running until interrupted"""
        try:
            while self.running:
                # Periodic cleanup of expired requests
                RequestManager.cleanup_expired()
                
                # Sleep for a while
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            print("\nBot stopped by user")
        except Exception as e:
            print(f"Bot error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the bot"""
        print("Stopping bot...")
        self.running = False
        
        if self.bot:
            await self.bot.stop()
        
        # Disconnect MongoDB
        disconnect_database()
        
        print("Bot stopped successfully")
    
    def run(self):
        """Run the bot (blocking)"""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            print("\nBot stopped by user")
        except Exception as e:
            print(f"Fatal error: {e}")
            import traceback
            traceback.print_exc()

def signal_handler(signum, frame):
    """Handle termination signals"""
    print(f"\nReceived signal {signum}, shutting down...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Main entry point"""
    # Check if running on Render
    is_render = "RENDER" in os.environ
    
    if is_render:
        print("Running on Render platform")
        
        # Render-specific optimizations
        CFG.connection_pool_size = 5
        CFG.scan_limit = 1000
        CFG.poll_seconds = 60
        
        # Run bot
        bot = UltraProMaxBot()
        bot.run()
    else:
        # Local development
        bot = UltraProMaxBot()
        bot.run()

if __name__ == "__main__":
    import os
    main()