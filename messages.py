"""
Rich message templates and formatters for Ultra Pro Max Bot
"""

import html
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from config import CFG

class MessageFormatter:
    """Formats messages with rich formatting and emojis"""
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape special characters for MarkdownV2"""
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        return ''.join(f'\\{char}' if char in escape_chars else char for char in text)
    
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML special characters"""
        return html.escape(text)
    
    @staticmethod
    def truncate(text: str, max_length: int = 200, suffix: str = "...") -> str:
        """Truncate text with ellipsis"""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

class CardBuilder:
    """Builds rich IMDb-style detail cards"""
    
    @staticmethod
    def build_movie_card(movie_data: Dict, matches: List[Dict] = None) -> Tuple[str, Optional[str]]:
        """Build detailed movie card"""
        return CardBuilder._build_media_card(movie_data, "movie", matches)
    
    @staticmethod
    def build_tv_card(tv_data: Dict, matches: List[Dict] = None) -> Tuple[str, Optional[str]]:
        """Build detailed TV show card"""
        return CardBuilder._build_media_card(tv_data, "tv", matches)
    
    @staticmethod
    def _build_media_card(media_data: Dict, media_type: str, matches: List[Dict] = None) -> Tuple[str, Optional[str]]:
        """
        Build a rich media card with all details
        
        Returns: (formatted_text, poster_url)
        """
        if not media_data:
            return "❌ No data available", None
        
        try:
            # Basic information
            if media_type == "movie":
                title = media_data.get("title", "Unknown Movie")
                original_title = media_data.get("original_title", "")
                tagline = media_data.get("tagline", "")
                runtime = media_data.get("runtime", 0)
                release_date = media_data.get("release_date", "")
                status = media_data.get("status", "Unknown")
                
                # Runtime formatting
                if runtime:
                    hours = runtime // 60
                    minutes = runtime % 60
                    runtime_text = f"{hours}h {minutes}m" if hours else f"{minutes}m"
                else:
                    runtime_text = "N/A"
                    
            else:  # TV Show
                title = media_data.get("name", "Unknown TV Show")
                original_title = media_data.get("original_name", "")
                tagline = ""
                runtime = 0
                runtime_text = "N/A"
                release_date = media_data.get("first_air_date", "")
                status = media_data.get("status", "Unknown")
                
                # Seasons and episodes
                seasons = media_data.get("number_of_seasons", 0)
                episodes = media_data.get("number_of_episodes", 0)
                runtime_text = f"{seasons} season{'s' if seasons != 1 else ''} • {episodes} episode{'s' if episodes != 1 else ''}"
            
            # Year extraction
            year = release_date[:4] if release_date else "N/A"
            
            # Rating information
            vote_average = media_data.get("vote_average", 0)
            vote_count = media_data.get("vote_count", 0)
            
            # Format rating with stars
            rating_stars = CardBuilder._get_rating_stars(vote_average)
            rating_text = f"**{vote_average:.1f}/10** {rating_stars} ({vote_count:,} votes)" if vote_average > 0 else "No ratings yet"
            
            # Genres
            genres = [g["name"] for g in media_data.get("genres", [])]
            genres_text = " • ".join(genres) if genres else "N/A"
            
            # Overview
            overview = media_data.get("overview", "No overview available.")
            if len(overview) > 500:
                overview = overview[:497] + "..."
            
            # Credits
            credits = media_data.get("credits", {})
            
            # Director (for movies) / Creator (for TV)
            if media_type == "movie":
                directors = []
                crew = credits.get("crew", [])
                for person in crew:
                    if person.get("job") == "Director":
                        directors.append(person.get("name", "Unknown"))
                director_text = ", ".join(directors[:3]) or "N/A"
            else:
                creators = media_data.get("created_by", [])
                creator_names = [c.get("name", "Unknown") for c in creators[:3]]
                director_text = ", ".join(creator_names) or "N/A"
            
            # Top cast (up to 8)
            cast = credits.get("cast", [])
            top_cast = []
            for person in cast[:8]:
                name = person.get("name", "Unknown")
                character = person.get("character", "")
                if character:
                    top_cast.append(f"**{name}** as _{character}_")
                else:
                    top_cast.append(f"**{name}**")
            cast_text = "\n".join(top_cast) if top_cast else "N/A"
            
            # Production companies
            companies = media_data.get("production_companies", [])
            company_names = [c.get("name", "") for c in companies[:3] if c.get("name")]
            companies_text = ", ".join(company_names) if company_names else "N/A"
            
            # Spoken languages
            languages = media_data.get("spoken_languages", [])
            language_names = [lang.get("english_name", "") for lang in languages[:3] if lang.get("english_name")]
            languages_text = ", ".join(language_names) if language_names else "N/A"
            
            # External IDs
            external_ids = media_data.get("external_ids", {})
            imdb_id = external_ids.get("imdb_id")
            imdb_url = f"https://www.imdb.com/title/{imdb_id}" if imdb_id else None
            
            # TMDB link
            tmdb_id = media_data.get("id", 0)
            tmdb_url = f"https://www.themoviedb.org/{media_type}/{tmdb_id}"
            
            # Poster URL
            poster_path = media_data.get("poster_path")
            
            # Videos (trailers)
            videos = media_data.get("videos", {}).get("results", [])
            youtube_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser")]
            
            # Build the card
            lines = []
            
            # Header section
            lines.append("🎬" + "─" * 38 + "🎬")
            
            # Title and year
            lines.append(f"<b>{title}</b>")
            if year != "N/A":
                lines.append(f"<i>{year}</i>")
            
            # Original title (if different)
            if original_title and original_title.lower() != title.lower():
                lines.append(f"<code>Original: {original_title}</code>")
            
            # Tagline (for movies)
            if tagline:
                lines.append(f"<i>\"{tagline}\"</i>")
            
            lines.append("")  # Empty line
            
            # Rating section
            lines.append("⭐ <b>Rating</b>")
            lines.append(rating_text)
            
            lines.append("")  # Empty line
            
            # Basic info block
            lines.append("📋 <b>Basic Information</b>")
            lines.append(f"• <b>Genres:</b> {genres_text}")
            lines.append(f"• <b>Status:</b> {status}")
            lines.append(f"• <b>Runtime:</b> {runtime_text}")
            
            if media_type == "movie":
                lines.append(f"• <b>Release Date:</b> {release_date}")
            else:
                lines.append(f"• <b>First Air Date:</b> {release_date}")
            
            lines.append(f"• <b>Production:</b> {companies_text}")
            lines.append(f"• <b>Languages:</b> {languages_text}")
            
            lines.append("")  # Empty line
            
            # Director/Creator
            if media_type == "movie":
                lines.append(f"🎬 <b>Director:</b> {director_text}")
            else:
                lines.append(f"📺 <b>Creator:</b> {director_text}")
            
            lines.append("")  # Empty line
            
            # Cast section
            lines.append("👥 <b>Top Cast</b>")
            lines.append(cast_text)
            
            lines.append("")  # Empty line
            
            # Overview section
            lines.append("📝 <b>Overview</b>")
            lines.append(overview)
            
            lines.append("")  # Empty line
            
            # Links section
            lines.append("🔗 <b>Links</b>")
            lines.append(f"• <a href='{tmdb_url}'>TMDB</a>")
            if imdb_url:
                lines.append(f"• <a href='{imdb_url}'>IMDb</a>")
                lines.append(f"• <b>IMDb ID:</b> <code>{imdb_id}</code>")
            
            # YouTube trailer
            if youtube_trailers:
                trailer = youtube_trailers[0]
                youtube_url = f"https://www.youtube.com/watch?v={trailer.get('key')}"
                lines.append(f"• <a href='{youtube_url}'>🎬 Watch Trailer</a>")
            
            lines.append("")  # Empty line
            
            # Availability section (if matches provided)
            if matches is not None:
                if matches:
                    lines.append("✅ <b>Available in Database</b>")
                    lines.append(f"Found {len(matches)} matching file(s):")
                    
                    for i, match in enumerate(matches[:3], 1):
                        filename = match.get("file_name", "Unknown")
                        score = match.get("score", 0)
                        quality = match.get("quality", "")
                        
                        # Truncate filename
                        if len(filename) > 40:
                            filename = filename[:37] + "..."
                        
                        line = f"{i}. <code>{filename}</code>"
                        if quality:
                            line += f" [{quality.upper()}]"
                        if CFG.debug_mode:
                            line += f" (score: {score:.2f})"
                        
                        lines.append(line)
                    
                    if len(matches) > 3:
                        lines.append(f"... and {len(matches) - 3} more")
                    
                    lines.append("")
                    lines.append("👉 Search in group to get download links")
                else:
                    lines.append("❌ <b>Not Available</b>")
                    lines.append("This content is not available in our database.")
                    lines.append("You can request it using the button below.")
            
            lines.append("")  # Empty line
            
            # Footer
            lines.append("─" * 40)
            lines.append(f"📡 <i>Powered by TMDB • {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>")
            
            formatted_text = "\n".join(lines)
            
            return formatted_text, poster_path
            
        except Exception as e:
            error_msg = "❌ <b>Error creating detail card</b>\n\n"
            error_msg += f"Title: {media_data.get('title', media_data.get('name', 'Unknown'))}\n"
            error_msg += f"Error: {str(e)[:100]}"
            return error_msg, None
    
    @staticmethod
    def _get_rating_stars(rating: float) -> str:
        """Convert rating to star emojis"""
        if rating <= 0:
            return "☆☆☆☆☆"
        
        # Convert 10-point scale to 5-star scale
        normalized = rating / 2
        
        full_stars = int(normalized)
        half_star = 1 if normalized - full_stars >= 0.5 else 0
        empty_stars = 5 - full_stars - half_star
        
        stars = "★" * full_stars
        if half_star:
            stars += "½"
        stars += "☆" * empty_stars
        
        return stars

class NotificationBuilder:
    """Builds notification messages"""
    
    @staticmethod
    def request_submitted(user_id: int, media_type: str, title: str, year: Optional[str]) -> str:
        """Build request submitted notification"""
        icon = "🎬" if media_type == "movie" else "📺"
        
        message = f"{icon} <b>Request Submitted</b>\n\n"
        message += f"<b>Title:</b> {title}"
        if year:
            message += f" ({year})"
        message += f"\n<b>Type:</b> {media_type.capitalize()}\n"
        message += f"<b>Status:</b> ⏳ Pending\n\n"
        message += "We'll notify you when this becomes available.\n"
        message += f"Requests expire after {CFG.request_expire_days} days."
        
        return message
    
    @staticmethod
    def request_filled(title: str, year: Optional[str], filename: str) -> str:
        """Build request filled notification"""
        message = "🎉 <b>Good News!</b>\n\n"
        message += "Your requested content is now available!\n\n"
        message += f"<b>Title:</b> {title}"
        if year:
            message += f" ({year})"
        message += f"\n<b>File:</b> <code>{MessageFormatter.truncate(filename, 50)}</code>\n\n"
        message += "👉 Search in the group to get download links.\n"
        message += "👉 Group එකේ search කරලා download links ගන්න."
        
        return message
    
    @staticmethod
    def admin_new_request(user_info: str, media_type: str, title: str, 
                         year: Optional[str], tmdb_link: str) -> str:
        """Build admin notification for new request"""
        icon = "🎬" if media_type == "movie" else "📺"
        
        message = f"📥 <b>NEW REQUEST</b>\n\n"
        message += f"<b>User:</b> {user_info}\n"
        message += f"{icon} <b>Type:</b> {media_type.upper()}\n"
        message += f"<b>Title:</b> {title}"
        if year:
            message += f" ({year})"
        message += f"\n<b>TMDB:</b> {tmdb_link}\n"
        message += f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return message

class HelpMessages:
    """Help and information messages"""
    
    @staticmethod
    def get_welcome_message() -> str:
        """Get welcome message for /start"""
        message = "👋 <b>Welcome to Ultra Pro Max Movie Finder!</b>\n\n"
        
        message += "🎬 <b>Features:</b>\n"
        message += "• Search movies/TV shows in group\n"
        message += "• Get detailed info in PM\n"
        message += "• Check availability in our database\n"
        message += "• Request unavailable content\n"
        message += "• Get notified when available\n\n"
        
        message += "⚡ <b>How to use:</b>\n"
        message += "1. Go to the authorized group\n"
        message += "2. Type a movie/series name\n"
        message += "3. Select from results\n"
        message += "4. View details in PM\n"
        message += "5. Request if not available\n\n"
        
        message += f"📊 <b>Limits:</b>\n"
        message += f"• Max requests: {CFG.max_requests_per_user} per user\n"
        message += f"• Request expires in: {CFG.request_expire_days} days\n\n"
        
        message += "🔧 <b>Support:</b>\n"
        message += "Contact @admin for help\n\n"
        
        message += "🚀 <b>සිංහලෙන්:</b>\n"
        message += "Group එකේ නමක් type කරන්න → Buttons එයි → Select කරන්න → "
        message += "PM එකට details එයි → තියෙනවද check කරන්න → නැත්තම් request කරන්න"
        
        return message
    
    @staticmethod
    def get_help_message() -> str:
        """Get help message"""
        message = "🆘 <b>Help Guide</b>\n\n"
        
        message += "🎯 <b>How to search:</b>\n"
        message += "1. Go to the authorized group\n"
        message += "2. Type movie/series name\n"
        message += "3. Select from results\n"
        message += "4. View details in PM\n\n"
        
        message += "📥 <b>How to request:</b>\n"
        message += "1. Search for content\n"
        message += "2. If not available, click 'Request' button\n"
        message += "3. Wait for notification when available\n\n"
        
        message += f"📊 <b>Your stats:</b>\n"
        message += f"• Max requests: {CFG.max_requests_per_user}\n"
        message += f"• Request expires in: {CFG.request_expire_days} days\n\n"
        
        message += "⚙️ <b>Commands:</b>\n"
        message += "/start - Start the bot\n"
        message += "/help - This help message\n"
        message += "/requests - View your requests\n"
        message += "/stats - View bot statistics\n"
        message += "/id - Get chat ID (group only)\n\n"
        
        message += "🔧 <b>Need help?</b> Contact @admin"
        
        return message
    
    @staticmethod
    def get_search_tips() -> str:
        """Get search tips"""
        message = "🔍 <b>Search Tips</b>\n\n"
        
        message += "💡 <b>For better results:</b>\n"
        message += "• Use English titles\n"
        message += "• Include year (e.g., Avengers 2012)\n"
        message += "• Check spelling\n"
        message += "• Try original title\n\n"
        
        message += "🎬 <b>Examples:</b>\n"
        message += "• Avengers Endgame\n"
        message += "• Game of Thrones\n"
        message += "• Harry Potter 2001\n"
        message += "• The Dark Knight\n\n"
        
        message += "📱 <b>සිංහලෙන්:</b>\n"
        message += "• ඉංග්‍රීසි නම් use කරන්න\n"
        message += "• වර්ෂය එකතු කරන්න\n"
        message += "• අකුරු පරීක්ෂා කරන්න"
        
        return message
    
    @staticmethod
    def get_request_guide() -> str:
        """Get request guide"""
        message = "📥 <b>Request Guide</b>\n\n"
        
        message += "✅ <b>How to request:</b>\n"
        message += "1. Search for content\n"
        message += "2. If not available, click 'Request' button\n"
        message += "3. Wait for notification\n\n"
        
        message += "⚠️ <b>Important:</b>\n"
        message += "• Requesting doesn't guarantee fulfillment\n"
        message += "• Depends on availability\n"
        message += "• Uploader's discretion\n"
        message += f"• Max {CFG.max_requests_per_user} pending requests\n\n"
        
        message += "⏰ <b>Request Status:</b>\n"
        message += "• ⏳ Pending - Waiting for upload\n"
        message += "• ✅ Done - Available now\n"
        message += "• ❌ Cancelled - Request cancelled\n"
        message += f"• ⏰ Expired - After {CFG.request_expire_days} days\n\n"
        
        message += "📱 <b>සිංහලෙන්:</b>\n"
        message += "• Search කරලා නැත්තම් request කරන්න\n"
        message += f"• Request {CFG.max_requests_per_user}ක් විතරක් ඉල්ලන්න පුළුවන්\n"
        message += "• Upload වුණා නම් notify කරනවා"
        
        return message

class StatsMessages:
    """Statistics messages"""
    
    @staticmethod
    def get_user_stats(user_data: Dict, request_count: int) -> str:
        """Get user statistics message"""
        message = "📊 <b>Your Statistics</b>\n\n"
        
        message += f"👤 <b>User Info:</b>\n"
        message += f"• ID: <code>{user_data.get('user_id', 'N/A')}</code>\n"
        message += f"• Name: {user_data.get('first_name', 'N/A')}\n"
        if user_data.get('username'):
            message += f"• Username: @{user_data['username']}\n"
        message += f"• First Seen: {user_data.get('first_seen', 'N/A')}\n"
        message += f"• Last Seen: {user_data.get('last_seen', 'N/A')}\n\n"
        
        message += f"📈 <b>Activity:</b>\n"
        message += f"• Total Requests: {user_data.get('requests_count', 0)}\n"
        message += f"• Pending Requests: {request_count}\n"
        message += f"• Messages Sent: {user_data.get('messages_count', 0)}\n\n"
        
        message += f"⚙️ <b>Limits:</b>\n"
        message += f"• Max Requests: {CFG.max_requests_per_user}\n"
        message += f"• Used: {request_count}/{CFG.max_requests_per_user}\n"
        
        return message
    
    @staticmethod
    def get_bot_stats(stats: Dict) -> str:
        """Get bot statistics message"""
        message = "🤖 <b>Bot Statistics</b>\n\n"
        
        message += "👥 <b>Users:</b>\n"
        message += f"• Total users: {stats.get('total_users', 0):,}\n"
        message += f"• Active today: {stats.get('active_today', 0):,}\n\n"
        
        message += "🎬 <b>Database:</b>\n"
        message += f"• Total files: {stats.get('total_files', 0):,}\n"
        message += f"• Total requests: {stats.get('total_requests', 0):,}\n"
        message += f"• Pending requests: {stats.get('pending_requests', 0):,}\n"
        message += f"• Completed requests: {stats.get('completed_requests', 0):,}\n\n"
        
        message += "📈 <b>Today's Activity:</b>\n"
        message += f"• Searches: {stats.get('searches_today', 0):,}\n"
        message += f"• Requests: {stats.get('requests_today', 0):,}\n"
        message += f"• Notifications: {stats.get('notifications_today', 0):,}\n\n"
        
        message += "⚡ <b>Performance:</b>\n"
        message += f"• Uptime: {stats.get('uptime', 'N/A')}\n"
        message += f"• Memory: {stats.get('memory_usage', 'N/A')}\n"
        message += f"• Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        return message

class ErrorMessages:
    """Error messages"""
    
    @staticmethod
    def get_error_message(error_type: str, details: str = "") -> str:
        """Get error message based on type"""
        messages = {
            "no_pm": "❌ <b>Cannot send to PM</b>\n\n"
                    "Please start the bot in PM first:\n"
                    "1. Click the button below\n"
                    "2. Press 'Start'\n"
                    "3. Try again",
            
            "request_limit": f"❌ <b>Request Limit Reached</b>\n\n"
                           f"You have reached the maximum of {CFG.max_requests_per_user} pending requests.\n"
                           "Please cancel some requests before making new ones.",
            
            "maintenance": "🔧 <b>Bot Under Maintenance</b>\n\n"
                          "The bot is currently undergoing maintenance.\n"
                          "Please try again later.\n\n"
                          "Estimated time: 30 minutes",
            
            "database": "💾 <b>Database Error</b>\n\n"
                       "There was an error accessing the database.\n"
                       "Please try again in a few minutes.",
            
            "tmdb": "🎬 <b>TMDB Error</b>\n\n"
                   "There was an error fetching data from TMDB.\n"
                   "Please try again later.",
            
            "not_found": "🔍 <b>Not Found</b>\n\n"
                        "No results found for your search.\n"
                        "Try:\n"
                        "• Different spelling\n"
                        "• English title\n"
                        "• Year (e.g., Avengers 2012)",
            
            "general": "⚠️ <b>An Error Occurred</b>\n\n"
                      "Please try again later.\n"
                      f"Error details: {details[:100]}"
        }
        
        return messages.get(error_type, messages["general"])

# Singleton instances for easy access
formatter = MessageFormatter()
cards = CardBuilder()
notifications = NotificationBuilder()
help_msgs = HelpMessages()
stats_msgs = StatsMessages()
errors = ErrorMessages()

# Export
__all__ = [
    'formatter', 'cards', 'notifications', 'help_msgs', 'stats_msgs', 'errors',
    'MessageFormatter', 'CardBuilder', 'NotificationBuilder', 
    'HelpMessages', 'StatsMessages', 'ErrorMessages'
]
