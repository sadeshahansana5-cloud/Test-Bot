"""
Private message handlers for Ultra Pro Max Bot
Handles commands and messages in private chat
"""

import asyncio
from typing import Optional, Dict, List
from datetime import datetime, timezone

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup

from config import CFG
from database import UserManager, RequestManager, StatsManager
from keyboards import KeyboardBuilder
from messages import help_msgs, stats_msgs, errors

class PrivateHandlers:
    """Handles all private chat interactions"""
    
    def __init__(self, bot: Client):
        self.bot = bot
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup private message handlers"""
        
        @self.bot.on_message(filters.command("start") & filters.private)
        async def handle_private_start(_, message: Message):
            await self.private_start_handler(message)
        
        @self.bot.on_message(filters.command("help") & filters.private)
        async def handle_private_help(_, message: Message):
            await self.private_help_handler(message)
        
        @self.bot.on_message(filters.command("requests") & filters.private)
        async def handle_private_requests(_, message: Message):
            await self.private_requests_handler(message)
        
        @self.bot.on_message(filters.command("stats") & filters.private)
        async def handle_private_stats(_, message: Message):
            await self.private_stats_handler(message)
        
        @self.bot.on_message(filters.command("broadcast") & filters.private)
        async def handle_broadcast(_, message: Message):
            await self.broadcast_handler(message)
        
        @self.bot.on_message(filters.command("admin") & filters.private)
        async def handle_admin(_, message: Message):
            await self.admin_handler(message)
    
    async def private_start_handler(self, message: Message):
        """Handle /start command in private chat"""
        
        # Register user
        UserManager.register_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        # Get welcome message
        welcome_text = help_msgs.get_welcome_message()
        
        # Send welcome message
        await message.reply_text(
            welcome_text,
            reply_markup=KeyboardBuilder.start_private_keyboard(),
            disable_web_page_preview=True
        )
        
        # Send quick start guide
        await asyncio.sleep(1)
        
        quick_guide = (
            "🚀 <b>Quick Start Guide</b>\n\n"
            "1. Go to our group:\n"
            f"   👉 <a href='https://t.me/+{abs(CFG.allowed_group_id)}'>Click here to join</a>\n\n"
            "2. Type a movie/series name\n"
            "3. Select from results\n"
            "4. I'll send details here in PM\n\n"
            "💡 <i>Try searching for 'Avengers' in the group!</i>"
        )
        
        await message.reply_text(
            quick_guide,
            disable_web_page_preview=True
        )
    
    async def private_help_handler(self, message: Message):
        """Handle /help command in private chat"""
        
        help_text = help_msgs.get_help_message()
        
        await message.reply_text(
            help_text,
            reply_markup=KeyboardBuilder.help_keyboard(),
            disable_web_page_preview=True
        )
    
    async def private_requests_handler(self, message: Message):
        """Handle /requests command in private chat"""
        
        user_id = message.from_user.id
        
        # Get user's pending requests
        pending_requests = RequestManager.get_user_requests(user_id, status="pending")
        
        if not pending_requests:
            no_requests_text = (
                "📭 <b>No Pending Requests</b>\n\n"
                "You haven't made any requests yet.\n\n"
                "💡 <b>How to request:</b>\n"
                "1. Search for content in the group\n"
                "2. If not available, click 'Request This'\n"
                "3. Wait for notification when available\n\n"
                "👉 <i>Go to the group and try searching!</i>"
            )
            
            await message.reply_text(
                no_requests_text,
                reply_markup=KeyboardBuilder.inline_search_keyboard("")
            )
            return
        
        # Build requests list
        requests_text = f"📋 <b>Your Pending Requests</b> ({len(pending_requests)}/{CFG.max_requests_per_user})\n\n"
        
        for i, req in enumerate(pending_requests, 1):
            title = req.get("title", "Unknown")
            year = req.get("year", "")
            media_type = req.get("media_type", "movie")
            created = req.get("created_at", datetime.now(timezone.utc))
            
            # Calculate days ago
            days_ago = (datetime.now(timezone.utc) - created).days
            
            icon = "🎬" if media_type == "movie" else "📺"
            requests_text += f"{i}. {icon} <b>{title}</b>"
            if year:
                requests_text += f" ({year})"
            requests_text += f"\n   ⏰ Requested {days_ago} day{'s' if days_ago != 1 else ''} ago\n\n"
        
        requests_text += (
            f"📊 <b>Total:</b> {len(pending_requests)}/{CFG.max_requests_per_user}\n"
            f"⏰ <b>Expires in:</b> {CFG.request_expire_days - days_ago if pending_requests else CFG.request_expire_days} days\n\n"
            "ℹ️ <i>Use the buttons below to manage requests</i>"
        )
        
        await message.reply_text(
            requests_text,
            reply_markup=KeyboardBuilder.request_management_keyboard(pending_requests),
            disable_web_page_preview=True
        )
    
    async def private_stats_handler(self, message: Message):
        """Handle /stats command in private chat"""
        
        user_id = message.from_user.id
        
        # Get user data
        user_data = UserManager.get_user(user_id) or {}
        
        # Get pending requests count
        pending_count = RequestManager.get_pending_requests_count(user_id)
        
        # Build user stats
        user_stats_text = stats_msgs.get_user_stats(user_data, pending_count)
        
        # Get bot stats
        from database import stats_col, users_col, requests_col, files_col
        
        try:
            total_users = users_col.count_documents({}) if users_col else 0
            total_files = files_col.count_documents({}) if files_col else 0
            total_requests = requests_col.count_documents({}) if requests_col else 0
            pending_requests = requests_col.count_documents({"status": "pending"}) if requests_col else 0
            
            bot_stats = {
                "total_users": total_users,
                "total_files": total_files,
                "total_requests": total_requests,
                "pending_requests": pending_requests,
                "uptime": "N/A",  # Will be calculated in main app
                "memory_usage": "N/A"
            }
            
            bot_stats_text = stats_msgs.get_bot_stats(bot_stats)
            
            # Combine stats
            full_stats_text = user_stats_text + "\n\n" + bot_stats_text
            
            await message.reply_text(
                full_stats_text,
                reply_markup=KeyboardBuilder.stats_keyboard(user_id),
                disable_web_page_preview=True
            )
            
        except Exception as e:
            # Fallback to user stats only
            await message.reply_text(
                user_stats_text,
                reply_markup=KeyboardBuilder.stats_keyboard(user_id),
                disable_web_page_preview=True
            )
    
    async def broadcast_handler(self, message: Message):
        """Handle /broadcast command (admin only)"""
        
        # Check if user is admin (replace with your admin check)
        if message.from_user.id not in [123456789, 987654321]:  # Your admin IDs
            await message.reply_text("❌ <b>Admin only command</b>")
            return
        
        # Check for message text
        if len(message.command) < 2:
            await message.reply_text(
                "📢 <b>Broadcast Message</b>\n\n"
                "Usage: <code>/broadcast &lt;message&gt;</code>\n\n"
                "Example:\n"
                "<code>/broadcast New movies added! Check them out.</code>"
            )
            return
        
        # Get broadcast message
        broadcast_text = " ".join(message.command[1:])
        
        # Confirmation
        confirm_text = (
            f"📢 <b>Confirm Broadcast</b>\n\n"
            f"<b>Message:</b>\n{broadcast_text}\n\n"
            f"<b>Recipients:</b> All users\n"
            f"<b>Estimated time:</b> 1-5 minutes\n\n"
            f"✅ Send to all users?"
        )
        
        await message.reply_text(
            confirm_text,
            reply_markup=KeyboardBuilder.confirmation_keyboard("broadcast", broadcast_text)
        )
    
    async def admin_handler(self, message: Message):
        """Handle /admin command (admin only)"""
        
        # Check if user is admin
        if message.from_user.id not in [123456789, 987654321]:  # Your admin IDs
            await message.reply_text("❌ <b>Admin only command</b>")
            return
        
        # Admin panel
        admin_text = (
            "⚙️ <b>Admin Panel</b>\n\n"
            "<b>Commands:</b>\n"
            "/broadcast - Send message to all users\n"
            "/stats - Detailed statistics\n"
            "/users - List all users\n"
            "/requests - Manage all requests\n"
            "/cleanup - Clean expired data\n\n"
            "<b>Quick Actions:</b>\n"
            "• View pending requests\n"
            "• Check database status\n"
            "• Monitor bot performance"
        )
        
        await message.reply_text(admin_text)

# Export handler setup function
def setup_private_handlers(bot: Client):
    """Setup private handlers"""
    return PrivateHandlers(bot)

__all__ = ['setup_private_handlers', 'PrivateHandlers']
