"""
Group message handlers for Ultra Pro Max Bot
Handles search queries in the authorized group
"""

import re
import asyncio
from typing import Optional, Dict, List
from datetime import datetime, timezone

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup

from config import CFG
from database import UserManager, StatsManager
from tmdb import search_tmdb
from keyboards import KeyboardBuilder
from messages import help_msgs, errors

# Cache to prevent spam
search_cache = {}
CACHE_TTL = 30  # seconds

class GroupHandlers:
    """Handles all group interactions"""
    
    def __init__(self, bot: Client):
        self.bot = bot
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup group message handlers"""
        
        @self.bot.on_message(filters.text & filters.group & ~filters.command(["start", "help", "id", "stats"]))
        async def handle_group_search(_, message: Message):
            await self.group_search_handler(message)
        
        @self.bot.on_message(filters.command("start") & filters.group)
        async def handle_group_start(_, message: Message):
            await self.group_start_handler(message)
        
        @self.bot.on_message(filters.command("help") & filters.group)
        async def handle_group_help(_, message: Message):
            await self.group_help_handler(message)
        
        @self.bot.on_message(filters.command("id") & filters.group)
        async def handle_group_id(_, message: Message):
            await self.group_id_handler(message)
        
        @self.bot.on_message(filters.command("stats") & filters.group)
        async def handle_group_stats(_, message: Message):
            await self.group_stats_handler(message)
    
    async def group_search_handler(self, message: Message):
        """Handle text messages in group for searching"""
        
        # Check if in allowed group
        if message.chat.id != CFG.allowed_group_id:
            return
        
        # Check for maintenance mode
        if CFG.maintenance_mode:
            await message.reply_text(
                errors.get_error_message("maintenance"),
                reply_markup=KeyboardBuilder.error_keyboard("maintenance")
            )
            return
        
        # Get search query
        query = message.text.strip()
        
        # Ignore very short queries
        if len(query) < 2:
            return
        
        # Ignore if looks like command
        if query.startswith("/"):
            return
        
        # Check cache to prevent spam
        cache_key = f"{message.from_user.id}:{query.lower()}"
        current_time = datetime.now(timezone.utc).timestamp()
        
        if cache_key in search_cache:
            last_time = search_cache[cache_key]
            if current_time - last_time < CACHE_TTL:
                # Too soon, ignore
                return
        
        # Update cache
        search_cache[cache_key] = current_time
        # Clean old cache entries
        self._clean_search_cache()
        
        # Register user activity
        UserManager.register_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        # Record search in stats
        StatsManager.record_search()
        
        # Send "searching" status
        searching_msg = await message.reply_text(
            "🔍 <i>Searching TMDB...</i>",
            quote=False
        )
        
        try:
            # Search TMDB
            results = search_tmdb(query)
            
            if not results:
                await searching_msg.delete()
                await message.reply_text(
                    errors.get_error_message("not_found"),
                    reply_markup=KeyboardBuilder.inline_search_keyboard(query)
                )
                return
            
            # Filter results to max allowed
            filtered_results = results[:CFG.max_search_results]
            
            # Prepare response
            if len(filtered_results) == 1:
                result = filtered_results[0]
                media_type = result.get("media_type", "movie")
                tmdb_id = result.get("id", 0)
                
                response_text = f"🎬 Found: <b>{result.get('title') or result.get('name')}</b>"
                
                # Send single result with detail button
                await searching_msg.delete()
                await message.reply_text(
                    response_text,
                    reply_markup=KeyboardBuilder.detail_keyboard(media_type, tmdb_id, False)
                )
                
            else:
                response_text = (
                    f"🔍 Found <b>{len(filtered_results)}</b> results for: <code>{query}</code>\n"
                    "Select the correct title:"
                )
                
                await searching_msg.delete()
                await message.reply_text(
                    response_text,
                    reply_markup=KeyboardBuilder.search_results_keyboard(filtered_results)
                )
            
            # Record result click in stats
            StatsManager.record_result_click()
            
        except Exception as e:
            await searching_msg.delete()
            
            error_text = errors.get_error_message("tmdb")
            if CFG.debug_mode:
                error_text += f"\n\n<code>Error: {str(e)[:100]}</code>"
            
            await message.reply_text(
                error_text,
                reply_markup=KeyboardBuilder.error_keyboard("general")
            )
    
    async def group_start_handler(self, message: Message):
        """Handle /start command in group"""
        
        welcome_text = (
            "🤖 <b>Ultra Pro Max Bot</b>\n\n"
            "I can help you find movies and TV shows!\n\n"
            "<b>How to use:</b>\n"
            "1. Type a movie/series name\n"
            "2. Select from results\n"
            "3. View details in PM\n\n"
            "<b>Commands:</b>\n"
            "/help - Show help\n"
            "/id - Show chat ID\n"
            "/stats - Bot statistics\n\n"
            "👉 <i>Start me in PM for full features!</i>"
        )
        
        await message.reply_text(
            welcome_text,
            reply_markup=KeyboardBuilder.start_group_keyboard()
        )
    
    async def group_help_handler(self, message: Message):
        """Handle /help command in group"""
        
        help_text = help_msgs.get_help_message()
        
        await message.reply_text(
            help_text,
            reply_markup=KeyboardBuilder.help_keyboard(),
            disable_web_page_preview=True
        )
    
    async def group_id_handler(self, message: Message):
        """Handle /id command in group"""
        
        chat_info = (
            f"📋 <b>Chat Information</b>\n\n"
            f"• <b>Title:</b> {message.chat.title or 'N/A'}\n"
            f"• <b>ID:</b> <code>{message.chat.id}</code>\n"
            f"• <b>Type:</b> {message.chat.type}\n"
        )
        
        if hasattr(message.chat, 'members_count'):
            chat_info += f"• <b>Members:</b> {message.chat.members_count}\n"
        
        if message.from_user:
            chat_info += f"\n👤 <b>Your ID:</b> <code>{message.from_user.id}</code>\n"
            if message.from_user.username:
                chat_info += f"• <b>Username:</b> @{message.from_user.username}\n"
        
        chat_info += (
            f"\n💡 <b>Note:</b> Use this ID in your .env file as ALLOWED_GROUP_ID"
        )
        
        await message.reply_text(chat_info)
    
    async def group_stats_handler(self, message: Message):
        """Handle /stats command in group"""
        
        from database import stats_col, users_col
        
        try:
            # Get basic stats
            total_users = users_col.count_documents({}) if users_col else 0
            total_files = 0  # We'll get this from files_col if available
            
            # Get today's stats
            today = datetime.now(timezone.utc).date().isoformat()
            today_stats = StatsManager.get_daily_stats(today)
            
            stats_text = (
                f"📊 <b>Group Statistics</b>\n\n"
                f"👥 <b>Users:</b> {total_users:,}\n"
                f"🔍 <b>Searches Today:</b> {today_stats.get('searches', 0):,}\n"
                f"📥 <b>Requests Today:</b> {today_stats.get('requests_created', 0):,}\n\n"
                f"⚡ <b>Features:</b>\n"
                f"• Search: {'✅' if CFG.enable_file_search else '❌'}\n"
                f"• Requests: {'✅' if CFG.enable_request_system else '❌'}\n"
                f"• Auto-notify: {'✅' if CFG.enable_auto_notify else '❌'}\n\n"
                f"🕒 <i>Last updated: {datetime.now().strftime('%H:%M:%S')}</i>"
            )
            
            await message.reply_text(
                stats_text,
                reply_markup=KeyboardBuilder.stats_keyboard(message.from_user.id if message.from_user else 0)
            )
            
        except Exception as e:
            error_text = errors.get_error_message("general", str(e))
            await message.reply_text(error_text)
    
    def _clean_search_cache(self):
        """Clean old entries from search cache"""
        current_time = datetime.now(timezone.utc).timestamp()
        to_remove = []
        
        for key, timestamp in search_cache.items():
            if current_time - timestamp > CACHE_TTL * 2:  # Double TTL for cleanup
                to_remove.append(key)
        
        for key in to_remove:
            del search_cache[key]

# Export handler setup function
def setup_group_handlers(bot: Client):
    """Setup group handlers"""
    return GroupHandlers(bot)

__all__ = ['setup_group_handlers', 'GroupHandlers']