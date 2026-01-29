"""
Advanced fuzzy matching algorithms for Sri Lankan movie file names
"""

import re
import math
from typing import List, Tuple, Dict, Optional, Set, Any
from difflib import SequenceMatcher
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MatchResult:
    """Result of a file matching operation"""
    file_name: str
    similarity_score: float
    matched_tokens: List[str]
    unmatched_tokens: List[str]
    year_match: bool
    quality_match: Optional[str]
    language_match: Optional[str]
    confidence: float  # 0.0 to 1.0
    
    def __str__(self):
        return (f"MatchResult(file={self.file_name[:30]}..., "
                f"score={self.similarity_score:.2f}, "
                f"confidence={self.confidence:.2f})")

class AdvancedMovieMatcher:
    """
    Advanced fuzzy matcher specifically optimized for Sri Lankan movie/TV show file names
    with support for common naming patterns in channels like:
    - RoyalMovies, RoyalSeries
    - CineSubz
    - MLWBD
    - TamilRockers
    - MoviezWorld
    """
    
    # Comprehensive list of junk words and patterns
    JUNK_WORDS = {
        # Quality indicators
        "480p", "720p", "1080p", "2160p", "4k", "8k", "hdr", "sdr", "uhd", "fhd", "hd", "sd",
        "10bit", "8bit", "hdr10", "hdr10plus", "dv", "dolbyvision", "bluray", "webrip", "webdl",
        "brrip", "dvdrip", "hdtv", "pdtv", "camrip", "ts", "telesync", "tc", "telecine", "scr",
        "screener", "dvdscr", "r5", "remux", "bdrip", "microhd", "complete", "full",
        
        # Codecs
        "x264", "x265", "h264", "h265", "hevc", "av1", "avc", "divx", "xvid",
        
        # Audio
        "aac", "ac3", "dd", "ddp", "dts", "eac3", "atmos", "truehd", "mp3", "flac", "ogg",
        
        # Language/Subtitles
        "sinhala", "sinhalese", "tamil", "telugu", "hindi", "malayalam", "kannada", "english",
        "dubbed", "dubbing", "dual", "multi", "sub", "subs", "subtitle", "subtitles",
        "embedded", "softsubs", "hardsub", "subtitled", "eng", "tam", "hin", "mal",
        
        # Common channel/uploader tags
        "cinesubz", "royalmovies", "royalseries", "mlwbd", "mkvcinemas", "moviezworld",
        "desiscandal", "khatrimaza", "worldfree4u", "bollyshare", "pagalmovies",
        "tamilrockers", "isaimini", "madrasrockers", "todaypk", "moviesda",
        "tamilyogi", "movieverse", "moviezindagi", "hdmovieshub", "skymovieshd",
        "yts", "rarbg", "ettv", "etrg", "ctrlhd", "framestor", "tigole",
        "team", "upload", "uploaded", "by", "from", "with", "latest", "new",
        
        # General noise
        "channel", "episode", "episodes", "season", "seasons", "series", "part", "volume",
        "collection", "edition", "version", "uncut", "uncensored", "directors", "extended",
        "unrated", "final", "complete", "full", "movie", "film", "theatrical", "cut", "limited",
        "special", "anniversary", "proper", "repack", "rerip", "nf", "amzn", "dsnp", "hulu", "atvp",
        
        # Website/domain parts
        "www", "com", "net", "org", "lk", "in", "to", "me", "co", "uk", "us", "tv", "website",
    }
    
    # Words that should be kept even if short
    KEEP_WORDS = {
        "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii",  # Roman numerals
        "tv", "us", "uk", "eu", "in", "at", "on", "of", "the", "and", "a", "an",  # Common words
        "3d", "2d", "4d",  # 3D/2D
        "dc", "uc",  # Director's Cut, Uncut
    }
    
    # Common abbreviations and their expansions
    ABBREVIATIONS = {
        "av": "avengers",
        "hp": "harry potter",
        "lotr": "lord of the rings",
        "sw": "star wars",
        "st": "star trek",
        "jw": "jurassic world",
        "jp": "jurassic park",
        "mi": "mission impossible",
        "ind": "indiana",
        "indy": "indiana",
        "ff": "fast furious",
        "tf": "transformers",
        "xmen": "x men",
        "got": "game of thrones",
        "tbbt": "big bang theory",
        "twd": "walking dead",
        "gotg": "guardians of the galaxy",
        "aou": "age of ultron",
        "cw": "civil war",
        "iw": "infinity war",
        "eg": "endgame",
    }
    
    # Quality patterns with scores
    QUALITY_PATTERNS = {
        "2160p": 1.0, "4k": 1.0, "uhd": 1.0,
        "1080p": 0.9, "fhd": 0.9,
        "720p": 0.8, "hd": 0.8,
        "480p": 0.6, "sd": 0.6,
        "bluray": 0.95, "remux": 0.97,
        "webdl": 0.85, "webrip": 0.8,
        "hdtv": 0.75, "dvdrip": 0.7,
        "cam": 0.3, "ts": 0.2, "telesync": 0.25,
    }
    
    # Language patterns
    LANGUAGE_PATTERNS = {
        "sinhala": "si", "sinhalese": "si",
        "tamil": "ta", "telugu": "te", 
        "hindi": "hi", "malayalam": "ml", "kannada": "kn",
        "english": "en", "dubbed": "dub", "dual": "dual",
    }
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.year_pattern = re.compile(r'\b(19\d{2}|20[0-2]\d)\b')
        self.quality_pattern = re.compile(r'\b(' + '|'.join(self.QUALITY_PATTERNS.keys()) + r')\b', re.IGNORECASE)
        self.language_pattern = re.compile(r'\b(' + '|'.join(self.LANGUAGE_PATTERNS.keys()) + r')\b', re.IGNORECASE)
        
        # Common prefixes to remove
        self.prefix_patterns = [
            r'^\[[^\]]+\]\s*',  # [Group]
            r'^\{[^}]+\}\s*',   # {Group}
            r'^\([^)]+\)\s*',   # (Group)
            r'^\d{4}p?\s*',     # Year at start
            r'^[A-Z0-9]{2,6}\s+',  # Short codes like PSA, A2M
            r'^@\w+\s*',        # @username
            r'^cine\w+\s+',     # cinesubz, cinehub
            r'^royal\w+\s+',    # royalmovies, royalseries
            r'^mlw\w+\s+',      # mlwbd
            r'^mkv\w+\s+',      # mkvcinemas
            r'^mov\w+\s+',      # moviezworld
        ]
        
        # File extensions
        self.extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts'}
    
    def normalize_filename(self, filename: str) -> Tuple[str, List[str], Optional[str], Dict[str, Any]]:
        """
        Advanced normalization of filename
        Returns: (normalized_string, tokens, year, metadata)
        """
        if not filename:
            return "", [], None, {}
        
        original = filename
        metadata = {
            "original": original,
            "quality": None,
            "language": None,
            "has_year": False,
            "has_quality": False,
            "has_language": False,
        }
        
        # Convert to lowercase
        text = filename.lower().strip()
        
        # Remove file extensions
        for ext in self.extensions:
            if text.endswith(ext):
                text = text[:-len(ext)].strip()
                break
        
        # Extract year
        year = None
        year_match = self.year_pattern.search(text)
        if year_match:
            year = year_match.group(1)
            text = self.year_pattern.sub(' ', text)
            metadata["has_year"] = True
        
        # Extract quality
        quality_match = self.quality_pattern.search(text)
        if quality_match:
            quality = quality_match.group(0).lower()
            text = self.quality_pattern.sub(' ', text)
            metadata["quality"] = quality
            metadata["has_quality"] = True
        
        # Extract language
        language_match = self.language_pattern.search(text)
        if language_match:
            language = language_match.group(0).lower()
            text = self.language_pattern.sub(' ', text)
            metadata["language"] = language
            metadata["has_language"] = True
        
        # Remove common prefixes
        for pattern in self.prefix_patterns:
            text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
        
        # Replace separators with spaces
        text = re.sub(r'[\._\-\[\]\(\)\{\}\|]', ' ', text)
        
        # Remove special characters but keep letters, numbers, and spaces
        text = re.sub(r'[^\w\s]', '', text)
        
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split into tokens
        tokens = text.split()
        
        # Process tokens
        filtered_tokens = []
        for token in tokens:
            # Skip empty tokens
            if not token:
                continue
            
            # Check if token should be kept
            if token in self.KEEP_WORDS:
                filtered_tokens.append(token)
                continue
            
            # Skip junk words
            if token in self.JUNK_WORDS:
                continue
            
            # Skip single characters (unless Roman numerals)
            if len(token) == 1 and token not in 'ivx':
                continue
            
            # Skip pure numbers (except years which we already extracted)
            if token.isdigit() and len(token) != 4:
                continue
            
            # Expand abbreviations
            if token in self.ABBREVIATIONS:
                filtered_tokens.extend(self.ABBREVIATIONS[token].split())
                continue
            
            # Remove numbers from mixed alphanumeric tokens (e.g., "movie123" -> "movie")
            if any(c.isdigit() for c in token):
                token = re.sub(r'\d+', '', token)
                if not token or len(token) < 2:
                    continue
            
            filtered_tokens.append(token)
        
        # Remove duplicate tokens while preserving order
        seen = set()
        unique_tokens = []
        for token in filtered_tokens:
            if token not in seen:
                seen.add(token)
                unique_tokens.append(token)
        
        normalized = ' '.join(unique_tokens)
        
        if self.debug:
            print(f"[DEBUG] Normalized '{original}' -> '{normalized}'")
            print(f"  Tokens: {unique_tokens}")
            print(f"  Year: {year}, Quality: {metadata['quality']}, Language: {metadata['language']}")
        
        return normalized, unique_tokens, year, metadata
    
    def calculate_similarity(self, tmdb_title: str, filename: str, 
                           tmdb_year: Optional[str] = None) -> MatchResult:
        """
        Calculate similarity between TMDB title and filename
        Returns a comprehensive MatchResult object
        """
        # Normalize TMDB title
        tmdb_norm, tmdb_tokens, _, _ = self.normalize_filename(tmdb_title)
        
        # Normalize filename
        file_norm, file_tokens, file_year, file_metadata = self.normalize_filename(filename)
        
        if not tmdb_tokens or not file_tokens:
            return MatchResult(
                file_name=filename,
                similarity_score=0.0,
                matched_tokens=[],
                unmatched_tokens=tmdb_tokens,
                year_match=False,
                quality_match=None,
                language_match=None,
                confidence=0.0
            )
        
        # Convert to sets for set operations
        tmdb_set = set(tmdb_tokens)
        file_set = set(file_tokens)
        
        # Calculate token-based metrics
        common_tokens = tmdb_set.intersection(file_set)
        unique_tmdb_tokens = tmdb_set - file_set
        unique_file_tokens = file_set - tmdb_set
        
        # Token coverage (how many TMDB tokens are found in file)
        token_coverage = len(common_tokens) / len(tmdb_set) if tmdb_set else 0.0
        
        # Sequence similarity
        sequence_similarity = SequenceMatcher(None, tmdb_norm, file_norm).ratio()
        
        # Jaccard similarity
        if tmdb_set or file_set:
            jaccard_similarity = len(common_tokens) / len(tmdb_set.union(file_set))
        else:
            jaccard_similarity = 0.0
        
        # Weighted similarity score
        base_score = (token_coverage * 0.5) + (sequence_similarity * 0.3) + (jaccard_similarity * 0.2)
        
        # Year matching bonus/penalty
        year_match = False
        if tmdb_year and file_year:
            if tmdb_year == file_year:
                base_score = min(1.0, base_score * 1.2)  # 20% bonus for exact year match
                year_match = True
            else:
                base_score *= 0.3  # Heavy penalty for wrong year
        
        elif tmdb_year and not file_year:
            # TMDB has year but file doesn't - moderate penalty
            base_score *= 0.7
        
        # Quality score adjustment
        quality_match = None
        if file_metadata["quality"]:
            quality_match = file_metadata["quality"]
            # Higher quality gets slight bonus
            quality_score = self.QUALITY_PATTERNS.get(quality_match.lower(), 0.5)
            base_score = min(1.0, base_score * (0.9 + (quality_score * 0.1)))
        
        # Language detection
        language_match = file_metadata["language"]
        
        # Length penalty for very short/long matches
        tmdb_len = len(tmdb_norm)
        file_len = len(file_norm)
        length_ratio = min(tmdb_len, file_len) / max(tmdb_len, file_len) if max(tmdb_len, file_len) > 0 else 0
        base_score *= length_ratio
        
        # Confidence calculation
        confidence = base_score
        
        # Boost confidence if token coverage is high
        if token_coverage >= 0.8:
            confidence = min(1.0, confidence * 1.1)
        
        # Penalize if too many unique file tokens (noise)
        if len(unique_file_tokens) > 5:
            confidence *= 0.8
        
        # Create match result
        result = MatchResult(
            file_name=filename,
            similarity_score=base_score,
            matched_tokens=list(common_tokens),
            unmatched_tokens=list(unique_tmdb_tokens),
            year_match=year_match,
            quality_match=quality_match,
            language_match=language_match,
            confidence=confidence
        )
        
        if self.debug:
            print(f"[DEBUG] Similarity for '{tmdb_title}' vs '{filename}':")
            print(f"  Base score: {base_score:.3f}")
            print(f"  Token coverage: {token_coverage:.2f} ({len(common_tokens)}/{len(tmdb_set)})")
            print(f"  Sequence: {sequence_similarity:.3f}, Jaccard: {jaccard_similarity:.3f}")
            print(f"  Year match: {year_match}, Quality: {quality_match}")
            print(f"  Confidence: {confidence:.3f}")
        
        return result
    
    def find_best_matches(self, tmdb_title: str, tmdb_year: Optional[str], 
                         file_names: List[str], limit: int = 5) -> List[MatchResult]:
        """
        Find best matching files from a list
        """
        matches = []
        
        for filename in file_names:
            result = self.calculate_similarity(tmdb_title, filename, tmdb_year)
            
            # Apply thresholds
            if tmdb_year:
                # With year - stricter matching
                if result.confidence >= 0.6:
                    matches.append(result)
            else:
                # Without year - require higher confidence
                if result.confidence >= 0.75:
                    matches.append(result)
        
        # Sort by confidence (descending)
        matches.sort(key=lambda x: x.confidence, reverse=True)
        
        # Remove duplicates (same normalized content)
        seen_content = set()
        unique_matches = []
        
        for match in matches:
            norm_content = ' '.join(sorted(match.matched_tokens))
            if norm_content not in seen_content:
                seen_content.add(norm_content)
                unique_matches.append(match)
                
                if len(unique_matches) >= limit:
                    break
        
        return unique_matches
    
    def extract_keywords(self, filename: str) -> Dict[str, Any]:
        """
        Extract keywords and metadata from filename
        """
        _, tokens, year, metadata = self.normalize_filename(filename)
        
        # Identify potential title keywords (longest tokens)
        title_keywords = []
        other_keywords = []
        
        for token in tokens:
            if len(token) >= 4:  # Longer tokens more likely to be title words
                title_keywords.append(token)
            else:
                other_keywords.append(token)
        
        # Sort by length (descending)
        title_keywords.sort(key=len, reverse=True)
        
        return {
            "title_keywords": title_keywords[:5],  # Top 5 longest tokens as potential title
            "other_keywords": other_keywords,
            "year": year,
            "quality": metadata["quality"],
            "language": metadata["language"],
            "token_count": len(tokens),
            "is_english": metadata["language"] in [None, "english", "en"],
        }

# Singleton instance
matcher = AdvancedMovieMatcher()

# Helper functions for external use
def normalize_movie_name(name: str) -> Tuple[str, Optional[str]]:
    """
    Quick normalization for movie/TV show names
    Returns: (normalized_name, year)
    """
    norm, tokens, year, _ = matcher.normalize_filename(name)
    return norm, year

def find_similar_files(tmdb_title: str, tmdb_year: Optional[str], 
                      file_names: List[str], limit: int = 5) -> List[Dict]:
    """
    Find similar files and return simplified results
    """
    matches = matcher.find_best_matches(tmdb_title, tmdb_year, file_names, limit)
    
    results = []
    for match in matches:
        results.append({
            "file_name": match.file_name,
            "score": match.similarity_score,
            "confidence": match.confidence,
            "year_match": match.year_match,
            "quality": match.quality_match,
            "language": match.language_match,
            "matched_tokens": match.matched_tokens,
            "unmatched_tokens": match.unmatched_tokens,
        })
    
    return results

def extract_file_metadata(filename: str) -> Dict[str, Any]:
    """
    Extract metadata from filename
    """
    return matcher.extract_keywords(filename)

# Export
__all__ = [
    'matcher', 'AdvancedMovieMatcher', 'MatchResult',
    'normalize_movie_name', 'find_similar_files', 'extract_file_metadata'
]
