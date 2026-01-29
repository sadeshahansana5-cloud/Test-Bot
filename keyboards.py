"""
Inline keyboard builders for Ultra Pro Max Bot
"""

from typing import List, Dict, Optional, Tuple
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CFG

class KeyboardBuilder:
    """Builds all inline keyboards for the bot"""
    
    @staticmethod
    def start_private_keyboard() -> InlineKeyboardMarkup:
        """Keyboard for /start command in private chat"""
        buttons = [
            [
                InlineKeyboardButton("🔍 Search Movies", switch_inline_query_current_chat=""),
                InlineKeyboardButton("📋 My Requests", callback_data="my_requests")
            ],
            [
                InlineKeyboardButton("📊 Stats", callback_data="stats"),
                InlineKeyboardButton("ℹ️ Help", callback_data="help")
            ],
            [
                InlineKeyboardButton("👥 Join Group", url=f"https://t.me/+{abs(CFG.allowed_group_id)}"),
                InlineKeyboardButton("🌟 Rate Bot", url="https://t.me/BotsArchive/6290")
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def start_group_keyboard() -> InlineKeyboardMarkup:
        """Keyboard for /start command in group"""
        username = CFG.bot_token.split(":")[0]  # Extract bot username from token
        buttons = [
            [
                InlineKeyboardButton("🤖 Start Bot", url=f"https://t.me/{username}?start=start"),
                InlineKeyboardButton("🔍 Search Now", switch_inline_query_current_chat="")
            ],
            [
                InlineKeyboardButton("📋 My Requests", url=f"https://t.me/{username}?start=requests")
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def search_results_keyboard(results: List[Dict], page: int = 1, total_pages: int = 1) -> InlineKeyboardMarkup:
        """Keyboard for search results pagination"""
        buttons = []
        
        # Add result buttons (max 10 per page)
        for result in results[:CFG.max_search_results]:
            media_type = result.get("media_type", "movie")
            tmdb_id = result.get("id", 0)
            
            # Get title and year
            if media_type == "movie":
                title = result.get("title", "Unknown")
                date = result.get("release_date", "")
            else:
                title = result.get("name", "Unknown")
                date = result.get("first_air_date", "")
            
            year = date[:4] if date else "----"
            
            # Truncate title if too long
            if len(title) > 35:
                title = title[:32] + "..."
            
            # Choose icon
            icon = "🎬" if media_type == "movie" else "📺"
            
            # Create button
            buttons.append([
                InlineKeyboardButton(
                    f"{icon} {title} ({year})",
                    callback_data=f"detail:{media_type}:{tmdb_id}:{page}"
                )
            ])
        
        # Add navigation buttons if there are multiple pages
        if total_pages > 1:
            nav_buttons = []
            
            # Previous button
            if page > 1:
                nav_buttons.append(
                    InlineKeyboardButton("⬅️ Previous", callback_data=f"search_page:{page-1}")
                )
            
            # Page indicator
            nav_buttons.append(
                InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop")
            )
            
            # Next button
            if page < total_pages:
                nav_buttons.append(
                    InlineKeyboardButton("Next ➡️", callback_data=f"search_page:{page+1}")
                )
            
            buttons.append(nav_buttons)
        
        # Add quick action buttons
        action_buttons = []
        
        if len(results) > 0:
            # First result as movie, second as TV (if available)
            movie_results = [r for r in results if r.get("media_type") == "movie"]
            tv_results = [r for r in results if r.get("media_type") == "tv"]
            
            if movie_results:
                action_buttons.append(
                    InlineKeyboardButton(
                        "🎬 Top Movie", 
                        callback_data=f"detail:movie:{movie_results[0]['id']}:{page}"
                    )
                )
            
            if tv_results:
                action_buttons.append(
                    InlineKeyboardButton(
                        "📺 Top TV", 
                        callback_data=f"detail:tv:{tv_results[0]['id']}:{page}"
                    )
                )
        
        if action_buttons:
            buttons.append(action_buttons)
        
        # Add close button
        buttons.append([
            InlineKeyboardButton("❌ Close", callback_data="close")
        ])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def detail_keyboard(media_type: str, tmdb_id: int, has_files: bool = False) -> InlineKeyboardMarkup:
        """Keyboard for detail view"""
        buttons = []
        
        if not has_files and CFG.enable_request_system:
            # Request button if no files available
            buttons.append([
                InlineKeyboardButton(
                    "📥 Request This", 
                    callback_data=f"request:{media_type}:{tmdb_id}"
                )
            ])
        
        # Action buttons
        action_row = []
        
        # Search similar
        action_row.append(
            InlineKeyboardButton(
                "🔍 Similar", 
                callback_data=f"similar:{media_type}:{tmdb_id}"
            )
        )
        
        # View on TMDB
        action_row.append(
            InlineKeyboardButton(
                "🌐 TMDB", 
                url=f"https://www.themoviedb.org/{media_type}/{tmdb_id}"
            )
        )
        
        buttons.append(action_row)
        
        # Search again
        buttons.append([
            InlineKeyboardButton(
                "🔎 Search Again", 
                switch_inline_query_current_chat=""
            )
        ])
        
        # Back to results (if we had a page context)
        buttons.append([
            InlineKeyboardButton("← Back to Results", callback_data="back_to_results")
        ])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def request_management_keyboard(requests: List[Dict]) -> InlineKeyboardMarkup:
        """Keyboard for managing user requests"""
        buttons = []
        
        if not requests:
            buttons.append([
                InlineKeyboardButton("🔍 Search Movies", switch_inline_query_current_chat="")
            ])
            return InlineKeyboardMarkup(buttons)
        
        # Add cancel buttons for each request
        for req in requests[:CFG.max_requests_per_user]:
            req_id = str(req.get("_id", ""))
            title = req.get("title", "Unknown")
            year = req.get("year", "")
            
            # Truncate title for button
            button_text = f"🗑 {title}"
            if year:
                button_text += f" ({year})"
            
            if len(button_text) > 30:
                button_text = button_text[:27] + "..."
            
            buttons.append([
                InlineKeyboardButton(button_text, callback_data=f"cancel_req:{req_id}")
            ])
        
        # Action buttons
        buttons.append([
            InlineKeyboardButton("🔍 Search More", switch_inline_query_current_chat=""),
            InlineKeyboardButton("📋 View All", callback_data="view_all_requests")
        ])
        
        # Close button
        buttons.append([
            InlineKeyboardButton("✅ Done", callback_data="close_requests")
        ])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def admin_actions_keyboard(media_type: str, tmdb_id: int, user_id: int) -> InlineKeyboardMarkup:
        """Keyboard for admin actions on requests"""
        buttons = [
            [
                InlineKeyboardButton(
                    "✅ Mark as Filled", 
                    callback_data=f"admin_fill:{media_type}:{tmdb_id}:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel Request", 
                    callback_data=f"admin_cancel:{media_type}:{tmdb_id}:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "👤 View User", 
                    callback_data=f"admin_view_user:{user_id}"
                ),
                InlineKeyboardButton(
                    "📊 Stats", 
                    callback_data=f"admin_stats:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔍 Search", 
                    switch_inline_query_current_chat=""
                )
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def file_results_keyboard(files: List[Dict], media_title: str, page: int = 1) -> InlineKeyboardMarkup:
        """Keyboard for displaying matching files"""
        buttons = []
        
        if not files:
            buttons.append([
                InlineKeyboardButton("😔 No Files Found", callback_data="noop")
            ])
            return InlineKeyboardMarkup(buttons)
        
        # Add file buttons
        for i, file_info in enumerate(files[:5], 1):
            filename = file_info.get("file_name", "Unknown")
            score = file_info.get("score", 0)
            quality = file_info.get("quality", "")
            
            # Truncate filename
            if len(filename) > 40:
                display_name = filename[:37] + "..."
            else:
                display_name = filename
            
            # Add quality indicator
            if quality:
                display_name = f"[{quality.upper()}] {display_name}"
            
            # Add score if in debug mode
            if CFG.debug_mode:
                display_name = f"{i}. {display_name} ({score:.2f})"
            else:
                display_name = f"{i}. {display_name}"
            
            buttons.append([
                InlineKeyboardButton(display_name, callback_data=f"file_info:{i}")
            ])
        
        # Navigation if more than 5 files
        if len(files) > 5:
            total_pages = (len(files) + 4) // 5  # Ceiling division
            
            nav_buttons = []
            if page > 1:
                nav_buttons.append(
                    InlineKeyboardButton("⬅️ Previous", callback_data=f"files_page:{page-1}:{media_title}")
                )
            
            nav_buttons.append(
                InlineKeyboardButton(f"📁 {page}/{total_pages}", callback_data="noop")
            )
            
            if page < total_pages:
                nav_buttons.append(
                    InlineKeyboardButton("Next ➡️", callback_data=f"files_page:{page+1}:{media_title}")
                )
            
            buttons.append(nav_buttons)
        
        # Action buttons
        buttons.append([
            InlineKeyboardButton("🔍 Search Again", switch_inline_query_current_chat=""),
            InlineKeyboardButton("📥 Request", callback_data=f"request_by_title:{media_title}")
        ])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def help_keyboard() -> InlineKeyboardMarkup:
        """Keyboard for help section"""
        buttons = [
            [
                InlineKeyboardButton("📖 How to Use", callback_data="help_usage"),
                InlineKeyboardButton("⚙️ Commands", callback_data="help_commands")
            ],
            [
                InlineKeyboardButton("🔍 Search Tips", callback_data="help_search"),
                InlineKeyboardButton("📥 Request Guide", callback_data="help_requests")
            ],
            [
                InlineKeyboardButton("👥 Support", url="https://t.me/UltraProMaxSupport"),
                InlineKeyboardButton("🌟 Rate", url="https://t.me/BotsArchive/6290")
            ],
            [
                InlineKeyboardButton("🏠 Home", callback_data="home"),
                InlineKeyboardButton("❌ Close", callback_data="close")
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def stats_keyboard(user_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
        """Keyboard for statistics view"""
        buttons = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats"),
                InlineKeyboardButton("📊 Detailed", callback_data="detailed_stats")
            ]
        ]
        
        if is_admin:
            buttons.append([
                InlineKeyboardButton("👥 User Stats", callback_data=f"admin_user_stats:{user_id}"),
                InlineKeyboardButton("📈 System", callback_data="admin_system_stats")
            ])
        
        buttons.append([
            InlineKeyboardButton("🏠 Home", callback_data="home"),
            InlineKeyboardButton("❌ Close", callback_data="close")
        ])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def confirmation_keyboard(action: str, data: str) -> InlineKeyboardMarkup:
        """Keyboard for confirmation dialogs"""
        buttons = [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"confirm_{action}:{data}"),
                InlineKeyboardButton("❌ No", callback_data="cancel_action")
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def language_keyboard() -> InlineKeyboardMarkup:
        """Keyboard for language selection"""
        buttons = [
            [
                InlineKeyboardButton("🇱🇰 Sinhala", callback_data="lang_si"),
                InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
            ],
            [
                InlineKeyboardButton("🇮🇳 Tamil", callback_data="lang_ta"),
                InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hi")
            ],
            [
                InlineKeyboardButton("🏠 Home", callback_data="home"),
                InlineKeyboardButton("❌ Close", callback_data="close")
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def quality_filter_keyboard() -> InlineKeyboardMarkup:
        """Keyboard for quality filtering"""
        buttons = [
            [
                InlineKeyboardButton("🎯 4K/UHD", callback_data="quality_4k"),
                InlineKeyboardButton("🔥 1080p/FHD", callback_data="quality_1080p")
            ],
            [
                InlineKeyboardButton("📺 720p/HD", callback_data="quality_720p"),
                InlineKeyboardButton("📱 480p/SD", callback_data="quality_480p")
            ],
            [
                InlineKeyboardButton("🎞️ Any Quality", callback_data="quality_any"),
                InlineKeyboardButton("🔙 Back", callback_data="back_to_search")
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def trending_keyboard() -> InlineKeyboardMarkup:
        """Keyboard for trending content"""
        buttons = [
            [
                InlineKeyboardButton("🔥 Trending Movies", callback_data="trending_movies"),
                InlineKeyboardButton("📺 Trending TV", callback_data="trending_tv")
            ],
            [
                InlineKeyboardButton("⭐ Top Rated", callback_data="top_rated"),
                InlineKeyboardButton("🎭 By Genre", callback_data="by_genre")
            ],
            [
                InlineKeyboardButton("🔍 Search", switch_inline_query_current_chat=""),
                InlineKeyboardButton("🏠 Home", callback_data="home")
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def genre_keyboard(genres: List[Dict]) -> InlineKeyboardMarkup:
        """Keyboard for genre selection"""
        buttons = []
        
        # Add genre buttons in rows of 2
        for i in range(0, len(genres), 2):
            row = []
            if i < len(genres):
                genre = genres[i]
                row.append(
                    InlineKeyboardButton(
                        genre.get("name", "Unknown"), 
                        callback_data=f"genre_{genre.get('id', 0)}"
                    )
                )
            
            if i + 1 < len(genres):
                genre = genres[i + 1]
                row.append(
                    InlineKeyboardButton(
                        genre.get("name", "Unknown"), 
                        callback_data=f"genre_{genre.get('id', 0)}"
                    )
                )
            
            if row:
                buttons.append(row)
        
        # Navigation buttons
        buttons.append([
            InlineKeyboardButton("🔙 Back", callback_data="back_to_trending"),
            InlineKeyboardButton("🏠 Home", callback_data="home")
        ])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def inline_search_keyboard(query: str) -> InlineKeyboardMarkup:
        """Keyboard for inline search results"""
        buttons = [
            [
                InlineKeyboardButton(
                    "🔍 Search in Group", 
                    switch_inline_query_current_chat=query
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 View Requests", 
                    callback_data="my_requests"
                ),
                InlineKeyboardButton(
                    "📊 Stats", 
                    callback_data="stats"
                )
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def error_keyboard(error_type: str = "general") -> InlineKeyboardMarkup:
        """Keyboard for error messages"""
        buttons = []
        
        if error_type == "no_pm":
            buttons = [
                [
                    InlineKeyboardButton("🤖 Start Bot in PM", url=f"https://t.me/{CFG.bot_token.split(':')[0]}?start=start")
                ],
                [
                    InlineKeyboardButton("❌ Close", callback_data="close")
                ]
            ]
        elif error_type == "maintenance":
            buttons = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
                    InlineKeyboardButton("📢 Updates", url="https://t.me/UltraProMaxUpdates")
                ]
            ]
        else:
            buttons = [
                [
                    InlineKeyboardButton("🔄 Try Again", callback_data="retry"),
                    InlineKeyboardButton("🏠 Home", callback_data="home")
                ]
            ]
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def close_keyboard() -> InlineKeyboardMarkup:
        """Simple close keyboard"""
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close")]])

# Helper functions
def get_search_query_keyboard(query: str) -> InlineKeyboardMarkup:
    """Get keyboard for search query"""
    return KeyboardBuilder.inline_search_keyboard(query)

def get_detail_actions_keyboard(media_type: str, tmdb_id: int, has_files: bool) -> InlineKeyboardMarkup:
    """Get keyboard for detail actions"""
    return KeyboardBuilder.detail_keyboard(media_type, tmdb_id, has_files)

def get_admin_keyboard(media_type: str, tmdb_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Get keyboard for admin actions"""
    return KeyboardBuilder.admin_actions_keyboard(media_type, tmdb_id, user_id)

# Export
__all__ = [
    'KeyboardBuilder',
    'get_search_query_keyboard',
    'get_detail_actions_keyboard',
    'get_admin_keyboard'
]
