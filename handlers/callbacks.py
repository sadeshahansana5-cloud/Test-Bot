"""
Callback query handlers for Ultra Pro Max Bot
Handles all inline button clicks
"""

import asyncio
import traceback
from typing import Optional, Dict, List
from datetime import datetime, timezone

from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup
from bson import ObjectId

from config import CFG
from database import UserManager, RequestManager, Cache, files_col
from tmdb import get_tmdb_details, build_detail_card, search_tmdb
from matcher import find_similar_files
from keyboards import KeyboardBuilder
from messages import cards, notifications, errors
from handlers.private import PrivateHandlers

class CallbackHandlers:
    """Handles all callback queries"""
    
    def __init__(self, bot: Client):
        self.bot = bot
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup callback query handlers"""
        
        @self.bot.on_callback_query()
        async def handle_callback(_, callback_query: CallbackQuery):
            await self.callback_handler(callback_query)
    
    async def callback_handler(self, callback_query: CallbackQuery):
        """Main callback query handler"""
        
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        # Register user activity
        UserManager.register_user(
            user_id,
            callback_query.from_user.username,
            callback_query.from_user.first_name,
            callback_query.from_user.last_name
        )
        
        try:
            if data.startswith("detail:"):
                await self.handle_detail_callback(callback_query)
            
            elif data.startswith("request:"):
                await self.handle_request_callback(callback_query)
            
            elif data.startswith("cancel_req:"):
                await self.handle_cancel_request_callback(callback_query)
            
            elif data.startswith("admin_fill:"):
                await self.handle_admin_fill_callback(callback_query)
            
            elif data.startswith("admin_cancel:"):
                await self.handle_admin_cancel_callback(callback_query)
            
            elif data.startswith("search_page:"):
                await self.handle_search_page_callback(callback_query)
            
            elif data.startswith("files_page:"):
                await self.handle_files_page_callback(callback_query)
            
            elif data.startswith("similar:"):
                await self.handle_similar_callback(callback_query)
            
            elif data.startswith("my_requests"):
                await self.handle_my_requests_callback(callback_query)
            
            elif data.startswith("stats"):
                await self.handle_stats_callback(callback_query)
            
            elif data.startswith("help"):
                await self.handle_help_callback(callback_query)
            
            elif data.startswith("confirm_"):
                await self.handle_confirmation_callback(callback_query)
            
            elif data.startswith("cancel_action"):
                await callback_query.answer("Action cancelled", show_alert=False)
                await callback_query.message.delete()
            
            elif data == "close":
                await callback_query.message.delete()
            
            elif data == "home":
                await self.handle_home_callback(callback_query)
            
            elif data == "noop":
                await callback_query.answer()
            
            else:
                await callback_query.answer("Unknown action", show_alert=True)
        
        except Exception as e:
            await self.handle_callback_error(callback_query, e)
    
    async def handle_detail_callback(self, callback_query: CallbackQuery):
        """Handle detail view callback"""
        try:
            # Parse callback data
            parts = callback_query.data.split(":")
            if len(parts) < 3:
                await callback_query.answer("Invalid data", show_alert=True)
                return
            
            _, media_type, tmdb_id_str = parts[:3]
            tmdb_id = int(tmdb_id_str)
            
            # Show loading alert
            await callback_query.answer("🔄 Loading details...", show_alert=False)
            
            # Get media details
            media_data = get_tmdb_details(media_type, tmdb_id)
            if not media_data:
                await callback_query.answer("❌ Error fetching details", show_alert=True)
                return
            
            # Get title and year for file matching
            if media_type == "movie":
                title = media_data.get("title", "Unknown")
                date = media_data.get("release_date", "")
            else:
                title = media_data.get("name", "Unknown")
                date = media_data.get("first_air_date", "")
            
            year = date[:4] if date else None
            
            # Check for matching files
            matches = []
            if CFG.enable_file_search and files_col:
                # Get sample files for matching
                sample_files = self._get_sample_files_for_matching(title[:20])
                matches = find_similar_files(title, year, sample_files, limit=3)
            
            # Build detail card
            detail_text, poster_path = cards.build_movie_card(
                media_data, matches
            ) if media_type == "movie" else cards.build_tv_card(
                media_data, matches
            )
            
            # Create keyboard
            has_files = len(matches) > 0
            keyboard = KeyboardBuilder.detail_keyboard(media_type, tmdb_id, has_files)
            
            # Send to user's PM
            try:
                if poster_path:
                    await self.bot.send_photo(
                        chat_id=callback_query.from_user.id,
                        photo=poster_path,
                        caption=detail_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                else:
                    await self.bot.send_message(
                        chat_id=callback_query.from_user.id,
                        text=detail_text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                
                await callback_query.answer("📨 Sent to your PM!", show_alert=False)
                
            except Exception as e:
                error_msg = errors.get_error_message("no_pm")
                await callback_query.answer("❌ Cannot send to PM", show_alert=True)
                
                # Send help message
                username = CFG.bot_token.split(":")[0]
                await callback_query.message.reply_text(
                    error_msg,
                    reply_markup=KeyboardBuilder.error_keyboard("no_pm")
                )
        
        except Exception as e:
            await callback_query.answer("❌ Error loading details", show_alert=True)
            raise
    
    async def handle_request_callback(self, callback_query: CallbackQuery):
        """Handle request callback"""
        try:
            # Parse callback data
            _, media_type, tmdb_id_str = callback_query.data.split(":", 2)
            tmdb_id = int(tmdb_id_str)
            user_id = callback_query.from_user.id
            
            # Check request limit
            pending_count = RequestManager.get_pending_requests_count(user_id)
            if pending_count >= CFG.max_requests_per_user:
                await callback_query.answer(
                    f"❌ Request limit reached ({pending_count}/{CFG.max_requests_per_user})",
                    show_alert=True
                )
                
                # Show user their pending requests
                pending_requests = RequestManager.get_user_requests(user_id, status="pending")
                await self.bot.send_message(
                    user_id,
                    "📋 <b>Your Pending Requests</b>\n\n"
                    f"You have {pending_count}/{CFG.max_requests_per_user} pending requests.\n"
                    "Please cancel some before making new ones:",
                    reply_markup=KeyboardBuilder.request_management_keyboard(pending_requests),
                    parse_mode="HTML"
                )
                return
            
            # Get media details
            media_data = get_tmdb_details(media_type, tmdb_id)
            if not media_data:
                await callback_query.answer("❌ Error fetching details", show_alert=True)
                return
            
            # Get title and year
            if media_type == "movie":
                title = media_data.get("title", "Unknown")
                date = media_data.get("release_date", "")
            else:
                title = media_data.get("name", "Unknown")
                date = media_data.get("first_air_date", "")
            
            year = date[:4] if date else None
            
            # Check if already available
            if CFG.enable_file_search and files_col:
                sample_files = self._get_sample_files_for_matching(title[:20])
                matches = find_similar_files(title, year, sample_files, limit=1)
                if matches:
                    await callback_query.answer(
                        "✅ Already available! Check details in PM.",
                        show_alert=True
                    )
                    return
            
            # Create request
            request_id = RequestManager.create_request(
                user_id, media_type, tmdb_id, title, year
            )
            
            if not request_id:
                await callback_query.answer("❌ Error creating request", show_alert=True)
                return
            
            # Notify admin channel
            if CFG.admin_req_channel_id:
                try:
                    tmdb_link = f"https://www.themoviedb.org/{media_type}/{tmdb_id}"
                    user_info = f"@{callback_query.from_user.username}" if callback_query.from_user.username else f"User #{user_id}"
                    
                    admin_message = notifications.admin_new_request(
                        user_info, media_type, title, year, tmdb_link
                    )
                    
                    await self.bot.send_message(
                        CFG.admin_req_channel_id,
                        admin_message,
                        reply_markup=KeyboardBuilder.admin_actions_keyboard(media_type, tmdb_id, user_id),
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    
                except Exception as e:
                    # Log error but continue
                    print(f"Error sending to admin channel: {e}")
            
            # Notify user
            await callback_query.answer(
                "✅ Request submitted! You'll be notified when available.",
                show_alert=True
            )
            
            # Send confirmation to user
            confirmation = notifications.request_submitted(user_id, media_type, title, year)
            await self.bot.send_message(
                user_id,
                confirmation,
                parse_mode="HTML"
            )
        
        except Exception as e:
            await callback_query.answer("❌ Error processing request", show_alert=True)
            raise
    
    async def handle_cancel_request_callback(self, callback_query: CallbackQuery):
        """Handle cancel request callback"""
        try:
            _, request_id = callback_query.data.split(":", 1)
            user_id = callback_query.from_user.id
            
            # Cancel request
            success = RequestManager.cancel_request(request_id, user_id)
            
            if success:
                await callback_query.answer("✅ Request cancelled", show_alert=True)
                await callback_query.message.delete()
                
                # Send confirmation
                await self.bot.send_message(
                    user_id,
                    "✅ Request cancelled successfully."
                )
            else:
                await callback_query.answer("❌ Error cancelling request", show_alert=True)
        
        except Exception as e:
            await callback_query.answer("❌ Error processing request", show_alert=True)
            raise
    
    async def handle_admin_fill_callback(self, callback_query: CallbackQuery):
        """Handle admin fill callback"""
        # Check if admin (simple check - implement proper admin check)
        if callback_query.from_user.id not in [123456789]:  # Replace with your admin ID
            await callback_query.answer("❌ Admin only", show_alert=True)
            return
        
        try:
            _, media_type, tmdb_id_str, user_id_str = callback_query.data.split(":", 3)
            tmdb_id = int(tmdb_id_str)
            user_id = int(user_id_str)
            
            # Mark requests as filled
            count = RequestManager.mark_requests_completed(media_type, tmdb_id)
            
            await callback_query.answer(
                f"✅ Marked {count} requests as filled",
                show_alert=True
            )
            
            # Update message
            await callback_query.message.edit_text(
                f"{callback_query.message.text}\n\n"
                f"✅ <b>Filled by admin</b>\n"
                f"• Requests completed: {count}\n"
                f"• Time: {datetime.now(timezone.utc).strftime('%H:%M:%S')}",
                parse_mode="HTML",
                reply_markup=None
            )
            
            # Notify user
            try:
                media_data = get_tmdb_details(media_type, tmdb_id)
                if media_data:
                    title = media_data.get("title") if media_type == "movie" else media_data.get("name")
                    await self.bot.send_message(
                        user_id,
                        f"🎉 <b>Good News!</b>\n\n"
                        f"Your request for <b>{title}</b> has been filled!\n"
                        f"Check the group for download links.",
                        parse_mode="HTML"
                    )
            except:
                pass
        
        except Exception as e:
            await callback_query.answer("❌ Error processing request", show_alert=True)
            raise
    
    async def handle_admin_cancel_callback(self, callback_query: CallbackQuery):
        """Handle admin cancel callback"""
        # Check if admin
        if callback_query.from_user.id not in [123456789]:  # Replace with your admin ID
            await callback_query.answer("❌ Admin only", show_alert=True)
            return
        
        try:
            _, media_type, tmdb_id_str, user_id_str = callback_query.data.split(":", 3)
            tmdb_id = int(tmdb_id_str)
            user_id = int(user_id_str)
            
            # Cancel user's requests for this media
            count = RequestManager.cancel_by_admin(media_type, tmdb_id, user_id)
            
            await callback_query.answer(
                f"✅ Cancelled {count} requests for user",
                show_alert=True
            )
            
            # Update message
            await callback_query.message.edit_text(
                f"{callback_query.message.text}\n\n"
                f"❌ <b>Cancelled by admin</b>\n"
                f"• User: {user_id}\n"
                f"• Requests cancelled: {count}\n"
                f"• Time: {datetime.now(timezone.utc).strftime('%H:%M:%S')}",
                parse_mode="HTML",
                reply_markup=None
            )
            
            # Notify user
            try:
                await self.bot.send_message(
                    user_id,
                    f"⚠️ <b>Request Cancelled</b>\n\n"
                    f"Your request was cancelled by admin.\n"
                    f"Contact @admin for more information.",
                    parse_mode="HTML"
                )
            except:
                pass
        
        except Exception as e:
            await callback_query.answer("❌ Error processing request", show_alert=True)
            raise
    
    async def handle_search_page_callback(self, callback_query: CallbackQuery):
        """Handle search pagination callback"""
        try:
            _, page_str = callback_query.data.split(":", 1)
            page = int(page_str)
            
            # Get original query from message
            message_text = callback_query.message.text
            # Extract query from message (assuming format: "Found X results for: query")
            if "for:" in message_text:
                query = message_text.split("for:")[1].strip()
                query = query.replace("<code>", "").replace("</code>", "").strip()
            else:
                query = ""
            
            if not query:
                await callback_query.answer("❌ Cannot paginate", show_alert=True)
                return
            
            # Search TMDB with new page
            results = search_tmdb(query, page)
            
            if not results:
                await callback_query.answer("❌ No more results", show_alert=True)
                return
            
            # Update message
            response_text = (
                f"🔍 Found <b>{len(results)}</b> results for: <code>{query}</code>\n"
                "Select the correct title:"
            )
            
            total_pages = 3  # TMDB typically returns up to 3 pages for free API
            await callback_query.message.edit_text(
                response_text,
                reply_markup=KeyboardBuilder.search_results_keyboard(results, page, total_pages),
                parse_mode="HTML"
            )
            
            await callback_query.answer(f"Page {page}", show_alert=False)
        
        except Exception as e:
            await callback_query.answer("❌ Error loading page", show_alert=True)
    
    async def handle_files_page_callback(self, callback_query: CallbackQuery):
        """Handle files pagination callback"""
        await callback_query.answer("Not implemented yet", show_alert=True)
    
    async def handle_similar_callback(self, callback_query: CallbackQuery):
        """Handle similar content callback"""
        await callback_query.answer("Not implemented yet", show_alert=True)
    
    async def handle_my_requests_callback(self, callback_query: CallbackQuery):
        """Handle my requests callback"""
        # Redirect to private handler
        from handlers.private import PrivateHandlers
        handler = PrivateHandlers(self.bot)
        await handler.private_requests_handler(callback_query.message)
        await callback_query.answer()
    
    async def handle_stats_callback(self, callback_query: CallbackQuery):
        """Handle stats callback"""
        # Redirect to private handler
        from handlers.private import PrivateHandlers
        handler = PrivateHandlers(self.bot)
        await handler.private_stats_handler(callback_query.message)
        await callback_query.answer()
    
    async def handle_help_callback(self, callback_query: CallbackQuery):
        """Handle help callback"""
        from handlers.private import PrivateHandlers
        handler = PrivateHandlers(self.bot)
        
        if callback_query.data == "help_usage":
            await self.bot.send_message(
                callback_query.from_user.id,
                "📖 <b>How to Use</b>\n\n"
                "1. Join our group\n"
                "2. Type movie/series name\n"
                "3. Select from results\n"
                "4. View details in PM\n"
                "5. Request if not available\n\n"
                "💡 <i>It's that simple!</i>",
                parse_mode="HTML"
            )
        elif callback_query.data == "help_commands":
            await self.bot.send_message(
                callback_query.from_user.id,
                "⚙️ <b>Commands</b>\n\n"
                "/start - Start the bot\n"
                "/help - Show this help\n"
                "/requests - View your requests\n"
                "/stats - View statistics\n"
                "/id - Get chat ID (group only)\n\n"
                "🔍 <b>Search Tips:</b>\n"
                "• Use English titles\n"
                "• Include year (e.g., Avengers 2012)\n"
                "• Check spelling",
                parse_mode="HTML"
            )
        else:
            await handler.private_help_handler(callback_query.message)
        
        await callback_query.answer()
    
    async def handle_confirmation_callback(self, callback_query: CallbackQuery):
        """Handle confirmation callbacks"""
        action, data = callback_query.data.split(":", 1)[0].replace("confirm_", ""), callback_query.data.split(":", 1)[1]
        
        if action == "broadcast":
            await self.handle_broadcast_confirmation(callback_query, data)
        else:
            await callback_query.answer("Unknown confirmation", show_alert=True)
    
    async def handle_broadcast_confirmation(self, callback_query: CallbackQuery, message_text: str):
        """Handle broadcast confirmation"""
        # Check if admin
        if callback_query.from_user.id not in [123456789]:  # Replace with your admin ID
            await callback_query.answer("❌ Admin only", show_alert=True)
            return
        
        await callback_query.answer("Starting broadcast...", show_alert=False)
        
        # Send to all users (simplified - in production, use batch processing)
        from database import users_col
        sent = 0
        failed = 0
        
        status_msg = await self.bot.send_message(
            callback_query.from_user.id,
            "📢 <b>Broadcast Started</b>\n\n"
            "Sending to all users...",
            parse_mode="HTML"
        )
        
        for user in users_col.find({}, {"user_id": 1}).limit(100):  # Limit for demo
            try:
                await self.bot.send_message(
                    user["user_id"],
                    f"📢 <b>Announcement</b>\n\n{message_text}",
                    parse_mode="HTML"
                )
                sent += 1
                
                # Rate limiting
                if sent % 10 == 0:
                    await asyncio.sleep(1)
                    await status_msg.edit_text(
                        f"📢 <b>Broadcast Progress</b>\n\n"
                        f"• ✅ Sent: {sent}\n"
                        f"• ❌ Failed: {failed}",
                        parse_mode="HTML"
                    )
                    
            except Exception:
                failed += 1
        
        await status_msg.edit_text(
            f"✅ <b>Broadcast Completed</b>\n\n"
            f"• ✅ Sent: {sent}\n"
            f"• ❌ Failed: {failed}\n\n"
            f"<i>Total users: {sent + failed}</i>",
            parse_mode="HTML"
        )
        
        await callback_query.message.delete()
    
    async def handle_home_callback(self, callback_query: CallbackQuery):
        """Handle home callback"""
        from handlers.private import PrivateHandlers
        handler = PrivateHandlers(self.bot)
        await handler.private_start_handler(callback_query.message)
        await callback_query.answer()
    
    async def handle_callback_error(self, callback_query: CallbackQuery, error: Exception):
        """Handle callback errors"""
        error_msg = errors.get_error_message("general", str(error))
        
        try:
            await callback_query.message.reply_text(
                error_msg,
                reply_markup=KeyboardBuilder.error_keyboard("general")
            )
        except:
            pass
        
        # Log error
        if CFG.debug_mode:
            print(f"Callback error: {error}")
            traceback.print_exc()
    
    def _get_sample_files_for_matching(self, query_prefix: str, limit: int = 100) -> List[str]:
        """Get sample files from database for matching"""
        if not files_col:
            return []
        
        try:
            # Search for files containing the query prefix
            cursor = files_col.find(
                {"file_name": {"$regex": query_prefix, "$options": "i"}},
                {"file_name": 1}
            ).limit(limit)
            
            return [doc.get("file_name", "") for doc in cursor if doc.get("file_name")]
        except Exception:
            return []

# Export handler setup function
def setup_callback_handlers(bot: Client):
    """Setup callback handlers"""
    return CallbackHandlers(bot)

__all__ = ['setup_callback_handlers', 'CallbackHandlers']
