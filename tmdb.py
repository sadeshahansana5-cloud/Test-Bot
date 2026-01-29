"""
TMDB API client with caching and rich detail card generation
"""

import re
import time
import requests
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple, Any
from urllib.parse import quote

from config import CFG
from database import Cache

class TMDBClient:
    """Advanced TMDB API client with intelligent caching and rate limiting"""
    
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
    
    # Cache keys
    CACHE_PREFIX_SEARCH = "tmdb_search:"
    CACHE_PREFIX_DETAILS = "tmdb_details:"
    CACHE_PREFIX_CONFIG = "tmdb_config"
    
    # Rate limiting
    RATE_LIMIT_REQUESTS = 40  # TMDB allows 40 requests per 10 seconds
    RATE_LIMIT_WINDOW = 10
    
    def __init__(self):
        self.api_key = CFG.tmdb_api_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"{CFG.app_name}/2.0 (Telegram Bot)",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate"
        })
        
        # Rate limiting state
        self.requests_made = 0
        self.window_start = time.time()
        self.lock = time.time()
        
        # Configuration cache
        self._config = None
        self._config_loaded = False
        self._genres_cache = {}
        
        # Load configuration on init
        self._load_configuration()
    
    def _rate_limit(self):
        """Implement rate limiting for TMDB API"""
        current_time = time.time()
        
        # Reset window if expired
        if current_time - self.window_start > self.RATE_LIMIT_WINDOW:
            self.requests_made = 0
            self.window_start = current_time
        
        # Check if we've exceeded the limit
        if self.requests_made >= self.RATE_LIMIT_REQUESTS:
            wait_time = self.RATE_LIMIT_WINDOW - (current_time - self.window_start)
            if wait_time > 0:
                time.sleep(wait_time + 0.5)  # Small buffer
                self.requests_made = 0
                self.window_start = time.time()
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None, 
                     retries: int = 3) -> Optional[Dict]:
        """Make a request to TMDB API with rate limiting and retries"""
        self._rate_limit()
        
        url = f"{self.BASE_URL}{endpoint}"
        params = params or {}
        params["api_key"] = self.api_key
        params.setdefault("language", "en-US")
        
        for attempt in range(retries):
            try:
                response = self.session.get(url, params=params, timeout=15)
                response.raise_for_status()
                
                self.requests_made += 1
                return response.json()
                
            except requests.exceptions.Timeout:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
                
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)
        
        return None
    
    def _load_configuration(self):
        """Load TMDB configuration (base URLs, image sizes, etc.)"""
        cache_key = f"{self.CACHE_PREFIX_CONFIG}"
        cached = Cache.get(cache_key)
        
        if cached is not None:
            self._config = cached
            self._config_loaded = True
            return
        
        try:
            data = self._make_request("/configuration")
            if data:
                self._config = data
                self._config_loaded = True
                # Cache for 24 hours
                Cache.set(cache_key, data, ttl=86400)
        except Exception:
            # Use fallback configuration
            self._config = {
                "images": {
                    "secure_base_url": "https://image.tmdb.org/t/p/",
                    "backdrop_sizes": ["w300", "w780", "w1280", "original"],
                    "poster_sizes": ["w92", "w154", "w185", "w342", "w500", "w780", "original"]
                }
            }
            self._config_loaded = False
    
    def search_multi(self, query: str, page: int = 1) -> List[Dict]:
        """
        Search for movies and TV shows
        
        Args:
            query: Search query
            page: Page number
            
        Returns:
            List of search results (movies and TV shows only)
        """
        if not query or len(query.strip()) < 2:
            return []
        
        cache_key = f"{self.CACHE_PREFIX_SEARCH}{quote(query.lower())}:{page}"
        cached = Cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            data = self._make_request("/search/multi", {
                "query": query,
                "page": page,
                "include_adult": "false"
            })
            
            if not data:
                return []
            
            # Filter only movies and TV shows
            results = []
            for item in data.get("results", []):
                media_type = item.get("media_type")
                if media_type in ("movie", "tv"):
                    # Add some calculated fields
                    item["_score"] = self._calculate_relevance_score(item, query)
                    results.append(item)
            
            # Sort by relevance score (if we calculated it)
            if all("_score" in r for r in results):
                results.sort(key=lambda x: x["_score"], reverse=True)
            
            # Cache for 1 hour
            Cache.set(cache_key, results, ttl=3600)
            return results
            
        except Exception:
            return []
    
    def _calculate_relevance_score(self, item: Dict, query: str) -> float:
        """Calculate relevance score for search results"""
        score = 0.0
        
        # Get title/name
        title = item.get("title") or item.get("name") or ""
        original_title = item.get("original_title") or item.get("original_name") or ""
        
        # Check exact matches
        query_lower = query.lower()
        title_lower = title.lower()
        original_lower = original_title.lower()
        
        if query_lower == title_lower:
            score += 100
        elif query_lower in title_lower:
            score += 50
        
        if query_lower == original_lower:
            score += 90
        elif query_lower in original_lower:
            score += 45
        
        # Popularity boost
        popularity = item.get("popularity", 0)
        if popularity:
            score += min(popularity / 10, 20)  # Cap at 20
        
        # Vote count boost
        vote_count = item.get("vote_count", 0)
        if vote_count > 1000:
            score += 10
        elif vote_count > 100:
            score += 5
        
        # Release date recency boost
        date_str = item.get("release_date") or item.get("first_air_date") or ""
        if date_str:
            try:
                release_year = int(date_str[:4])
                current_year = datetime.now().year
                if release_year >= current_year - 1:  # Recent releases
                    score += 15
                elif release_year >= current_year - 5:  # Fairly recent
                    score += 5
            except:
                pass
        
        return score
    
    def get_details(self, media_type: str, tmdb_id: int) -> Optional[Dict]:
        """
        Get detailed information for a movie or TV show
        
        Args:
            media_type: 'movie' or 'tv'
            tmdb_id: TMDB ID
            
        Returns:
            Detailed information dictionary or None
        """
        if media_type not in ("movie", "tv"):
            return None
        
        cache_key = f"{self.CACHE_PREFIX_DETAILS}{media_type}:{tmdb_id}"
        cached = Cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            # Append all relevant details
            append_to_response = [
                "credits",           # Cast and crew
                "external_ids",      # IMDb, Facebook, Instagram, etc.
                "images",           # Posters, backdrops
                "videos",           # Trailers, teasers
                "content_ratings",  # Age ratings
                "release_dates",    # Release dates by country (movies)
                "similar",          # Similar movies/shows
                "recommendations"   # Recommendations
            ]
            
            if media_type == "tv":
                append_to_response.extend(["keywords", "episode_groups"])
            
            data = self._make_request(f"/{media_type}/{tmdb_id}", {
                "append_to_response": ",".join(append_to_response)
            })
            
            if data:
                # Cache for 6 hours
                Cache.set(cache_key, data, ttl=21600)
                return data
            
        except Exception:
            pass
        
        return None
    
    def get_poster_url(self, poster_path: Optional[str], size: str = "w500") -> Optional[str]:
        """
        Get full URL for a poster image
        
        Args:
            poster_path: Poster path from TMDB
            size: Image size (w92, w154, w185, w342, w500, w780, original)
            
        Returns:
            Full image URL or None
        """
        if not poster_path:
            return None
        
        if self._config_loaded and self._config:
            base_url = self._config["images"]["secure_base_url"]
        else:
            base_url = "https://image.tmdb.org/t/p/"
        
        return f"{base_url}{size}{poster_path}"
    
    def get_backdrop_url(self, backdrop_path: Optional[str], size: str = "w1280") -> Optional[str]:
        """
        Get full URL for a backdrop image
        
        Args:
            backdrop_path: Backdrop path from TMDB
            size: Image size (w300, w780, w1280, original)
            
        Returns:
            Full image URL or None
        """
        if not backdrop_path:
            return None
        
        if self._config_loaded and self._config:
            base_url = self._config["images"]["secure_base_url"]
        else:
            base_url = "https://image.tmdb.org/t/p/"
        
        return f"{base_url}{size}{backdrop_path}"
    
    def build_rich_card(self, media_data: Dict, media_type: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Build a rich detail card (IMDb-style) with all information
        
        Args:
            media_data: Media data from get_details()
            media_type: 'movie' or 'tv'
            
        Returns:
            Tuple of (formatted_text, poster_url, backdrop_url)
        """
        if not media_data:
            return "Error: No data available", None, None
        
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
                seasons_text = f"{seasons} season{'s' if seasons != 1 else ''}"
                episodes_text = f"{episodes} episode{'s' if episodes != 1 else ''}"
            
            # Year extraction
            year = release_date[:4] if release_date else "N/A"
            
            # Rating information
            vote_average = media_data.get("vote_average", 0)
            vote_count = media_data.get("vote_count", 0)
            
            # Format rating with stars
            rating_stars = self._format_rating_stars(vote_average)
            rating_text = f"**{vote_average:.1f}/10** ⭐ ({vote_count:,} votes)" if vote_average > 0 else "No ratings yet"
            
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
                    top_cast.append(f"**{name}** as {character}")
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
            
            # Poster and backdrop URLs
            poster_path = media_data.get("poster_path")
            poster_url = self.get_poster_url(poster_path, "w500") if poster_path else None
            
            backdrop_path = media_data.get("backdrop_path")
            backdrop_url = self.get_backdrop_url(backdrop_path, "w780") if backdrop_path else None
            
            # Videos (trailers)
            videos = media_data.get("videos", {}).get("results", [])
            youtube_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser")]
            
            # Build the rich card
            lines = []
            
            # Header with title and year
            lines.append(f"🎬 **{title}** ({year})")
            
            # Original title (if different)
            if original_title and original_title.lower() != title.lower():
                lines.append(f"🎭 *Original Title:* {original_title}")
            
            # Tagline (for movies)
            if tagline:
                lines.append(f"💫 *\"{tagline}\"*")
            
            lines.append("")  # Empty line
            
            # Rating and votes
            lines.append(f"⭐ **Rating:** {rating_text}")
            lines.append(f"{rating_stars}")
            
            lines.append("")  # Empty line
            
            # Basic info block
            lines.append("📋 **Basic Information**")
            lines.append(f"• **Genres:** {genres_text}")
            lines.append(f"• **Status:** {status}")
            
            if media_type == "movie":
                lines.append(f"• **Runtime:** {runtime_text}")
                lines.append(f"• **Release Date:** {release_date}")
            else:
                lines.append(f"• **Seasons:** {seasons_text} ({episodes_text})")
                lines.append(f"• **First Air Date:** {release_date}")
            
            lines.append(f"• **Production:** {companies_text}")
            lines.append(f"• **Languages:** {languages_text}")
            
            lines.append("")  # Empty line
            
            # Director/Creator
            if media_type == "movie":
                lines.append(f"🎬 **Director:** {director_text}")
            else:
                lines.append(f"📺 **Creator:** {director_text}")
            
            lines.append("")  # Empty line
            
            # Cast
            lines.append("👥 **Top Cast:**")
            lines.append(cast_text)
            
            lines.append("")  # Empty line
            
            # Overview
            lines.append("📝 **Overview:**")
            lines.append(overview)
            
            lines.append("")  # Empty line
            
            # External links
            lines.append("🔗 **Links:**")
            lines.append(f"• **TMDB:** {tmdb_url}")
            if imdb_url:
                lines.append(f"• **IMDb:** {imdb_url}")
                lines.append(f"• **IMDb ID:** `{imdb_id}`")
            
            # YouTube trailers
            if youtube_trailers:
                trailer = youtube_trailers[0]
                youtube_url = f"https://www.youtube.com/watch?v={trailer.get('key')}"
                lines.append(f"• **Trailer:** {youtube_url}")
            
            # Additional information section
            lines.append("")  # Empty line
            lines.append("📊 **Additional Info**")
            
            # Budget and revenue (for movies)
            if media_type == "movie":
                budget = media_data.get("budget", 0)
                revenue = media_data.get("revenue", 0)
                
                if budget > 0:
                    lines.append(f"• **Budget:** ${budget:,}")
                if revenue > 0:
                    lines.append(f"• **Revenue:** ${revenue:,}")
            
            # Homepage (if available)
            homepage = media_data.get("homepage")
            if homepage:
                lines.append(f"• **Homepage:** {homepage[:50]}{'...' if len(homepage) > 50 else ''}")
            
            # Content rating
            content_ratings = media_data.get("content_ratings", {}).get("results", [])
            us_rating = next((r for r in content_ratings if r.get("iso_3166_1") == "US"), None)
            if us_rating:
                lines.append(f"• **US Rating:** {us_rating.get('rating', 'N/A')}")
            
            # Footer
            lines.append("")  # Empty line
            lines.append("─" * 40)
            lines.append("💡 *Tip: Use the buttons below to request or search again*")
            
            formatted_text = "\n".join(lines)
            
            return formatted_text, poster_url, backdrop_url
            
        except Exception as e:
            error_msg = f"❌ **Error creating detail card**\n\n"
            error_msg += f"Title: {media_data.get('title', media_data.get('name', 'Unknown'))}\n"
            error_msg += f"Error: {str(e)[:100]}"
            return error_msg, None, None
    
    def _format_rating_stars(self, rating: float) -> str:
        """Format rating as stars (★)"""
        if rating <= 0:
            return "☆☆☆☆☆"
        
        full_stars = int(rating / 2)  # Convert 10-point scale to 5-star scale
        half_star = 1 if (rating / 2) - full_stars >= 0.5 else 0
        empty_stars = 5 - full_stars - half_star
        
        stars = "★" * full_stars
        if half_star:
            stars += "½"
        stars += "☆" * empty_stars
        
        return stars
    
    def get_genres(self, media_type: str) -> List[Dict]:
        """Get genre list for movies or TV shows"""
        if media_type not in ("movie", "tv"):
            return []
        
        cache_key = f"tmdb_genres:{media_type}"
        
        if cache_key in self._genres_cache:
            return self._genres_cache[cache_key]
        
        cached = Cache.get(cache_key)
        if cached is not None:
            self._genres_cache[cache_key] = cached
            return cached
        
        try:
            data = self._make_request(f"/genre/{media_type}/list")
            if data and "genres" in data:
                genres = data["genres"]
                Cache.set(cache_key, genres, ttl=86400)  # 24 hours
                self._genres_cache[cache_key] = genres
                return genres
        except Exception:
            pass
        
        return []
    
    def get_trending(self, media_type: str = "all", time_window: str = "week") -> List[Dict]:
        """Get trending movies/TV shows"""
        if media_type not in ("all", "movie", "tv"):
            media_type = "all"
        if time_window not in ("day", "week"):
            time_window = "week"
        
        cache_key = f"tmdb_trending:{media_type}:{time_window}"
        cached = Cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            data = self._make_request(f"/trending/{media_type}/{time_window}", {"page": 1})
            if data and "results" in data:
                results = data["results"]
                # Filter only movies/TV if media_type is "all"
                if media_type == "all":
                    results = [r for r in results if r.get("media_type") in ("movie", "tv")]
                
                Cache.set(cache_key, results, ttl=3600)  # 1 hour
                return results
        except Exception:
            pass
        
        return []
    
    def get_similar(self, media_type: str, tmdb_id: int, limit: int = 5) -> List[Dict]:
        """Get similar movies/TV shows"""
        cache_key = f"tmdb_similar:{media_type}:{tmdb_id}"
        cached = Cache.get(cache_key)
        
        if cached is not None:
            return cached[:limit]
        
        try:
            data = self._make_request(f"/{media_type}/{tmdb_id}/similar", {"page": 1})
            if data and "results" in data:
                results = data["results"]
                Cache.set(cache_key, results, ttl=7200)  # 2 hours
                return results[:limit]
        except Exception:
            pass
        
        return []
    
    def format_duration(self, minutes: int) -> str:
        """Format duration in minutes to human readable format"""
        if not minutes:
            return "N/A"
        
        hours = minutes // 60
        mins = minutes % 60
        
        if hours == 0:
            return f"{mins}m"
        elif mins == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {mins}m"

# Global TMDB client instance
tmdb_client = TMDBClient()

# Helper functions for external use
def search_tmdb(query: str) -> List[Dict]:
    """Search TMDB for movies and TV shows"""
    return tmdb_client.search_multi(query)

def get_tmdb_details(media_type: str, tmdb_id: int) -> Optional[Dict]:
    """Get detailed information from TMDB"""
    return tmdb_client.get_details(media_type, tmdb_id)

def build_detail_card(media_data: Dict, media_type: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Build rich detail card for a movie/TV show"""
    return tmdb_client.build_rich_card(media_data, media_type)

def get_poster_url(poster_path: Optional[str]) -> Optional[str]:
    """Get full poster URL"""
    return tmdb_client.get_poster_url(poster_path)

# Export
__all__ = [
    'tmdb_client', 'TMDBClient',
    'search_tmdb', 'get_tmdb_details', 'build_detail_card', 'get_poster_url'
]
