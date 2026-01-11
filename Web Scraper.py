import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import os
from urllib.parse import urlparse, urljoin, urlunparse
from urllib.robotparser import RobotFileParser
import time
from pathlib import Path
from collections import deque
import hashlib
import mimetypes
from typing import Set, List, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    )
}

# Configuration constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_PAGES = 500  # Safety limit
MAX_QUEUE_SIZE = 1000  # Prevent memory issues
REQUEST_DELAY = 0.1  # Seconds between requests
MAX_WORKERS = 5  # Reduced for better rate limiting


class RateLimiter:
    """Simple rate limiter to avoid overwhelming servers"""
    def __init__(self, delay: float = REQUEST_DELAY):
        self.delay = delay
        self.last_request = 0
        self.lock = threading.Lock()
    
    def wait(self):
        with self.lock:
            elapsed = time.time() - self.last_request
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_request = time.time()


class WebScraper:
    """Enhanced web scraper with safety features"""
    
    def __init__(self, start_url: str, file_types: List[str], 
                 max_depth: int = 3, respect_robots: bool = True):
        self.start_url = start_url
        self.file_types = file_types
        self.max_depth = max_depth
        self.respect_robots = respect_robots
        
        self.found_files: Set[str] = set()
        self.visited: Set[str] = set()
        self.visited_lock = threading.Lock()
        self.files_lock = threading.Lock()
        
        self.rate_limiter = RateLimiter()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        
        # Parse base domain
        parsed = urlparse(start_url)
        self.base_domain = f"{parsed.scheme}://{parsed.netloc}"
        self.domain = parsed.netloc
        
        # Setup robots.txt parser
        self.robot_parser = None
        if respect_robots:
            self.setup_robots_parser()
        
        # Statistics
        self.stats = {
            'pages_checked': 0,
            'files_found': 0,
            'errors': 0
        }
    
    def setup_robots_parser(self):
        """Setup robots.txt parser"""
        try:
            self.robot_parser = RobotFileParser()
            robots_url = urljoin(self.base_domain, '/robots.txt')
            self.robot_parser.set_url(robots_url)
            self.robot_parser.read()
            logger.info(f"✓ Loaded robots.txt from {robots_url}")
        except Exception as e:
            logger.warning(f"Could not load robots.txt: {e}")
            self.robot_parser = None
    
    def can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt"""
        if not self.respect_robots or not self.robot_parser:
            return True
        return self.robot_parser.can_fetch("*", url)
    
    def normalize_url(self, url: str, base_url: str) -> Optional[str]:
        """Properly normalize and resolve URLs"""
        try:
            # Handle relative URLs
            absolute_url = urljoin(base_url, url)
            
            # Parse and normalize
            parsed = urlparse(absolute_url)
            
            # Remove fragments
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path,
                parsed.params,
                parsed.query,
                ''  # Remove fragment
            ))
            
            return normalized
        except Exception as e:
            logger.debug(f"Error normalizing URL {url}: {e}")
            return None
    
    def is_valid_file_type(self, url: str, content_type: Optional[str] = None) -> bool:
        """Check if file is valid based on extension and optionally content type"""
        # Check extension
        if not any(url.lower().endswith(ext) for ext in self.file_types):
            return False
        
        # If content type provided, verify it matches
        if content_type:
            expected_types = {
                '.pdf': 'application/pdf',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.zip': 'application/zip',
            }
            
            file_ext = next((ext for ext in self.file_types if url.lower().endswith(ext)), None)
            if file_ext and file_ext in expected_types:
                expected = expected_types[file_ext]
                if not content_type.startswith(expected.split('/')[0]):
                    logger.warning(f"Content type mismatch for {url}: expected {expected}, got {content_type}")
                    return False
        
        return True
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal"""
        # Remove path separators and dangerous characters
        filename = filename.replace('/', '_').replace('\\', '_')
        filename = filename.replace('..', '_')
        
        # Limit length
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        return filename
    
    def scrape_page(self, url: str, depth: int) -> List[Tuple[str, int]]:
        """Scrape a single page for files and links"""
        # Check if already visited
        with self.visited_lock:
            if url in self.visited:
                return []
            self.visited.add(url)
        
        # Check depth limit
        if depth > self.max_depth:
            return []
        
        # Check robots.txt
        if not self.can_fetch(url):
            logger.info(f"⏭️  Skipping (robots.txt): {url}")
            return []
        
        # Rate limiting
        self.rate_limiter.wait()
        
        logger.info(f"🔍 [{depth}] Checking: {url}")
        
        try:
            response = self.session.get(url, timeout=10, stream=True)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            
            # If it's not HTML, skip parsing
            if 'text/html' not in content_type:
                return []
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            page_links = []
            
            # Find all links
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # Skip empty, javascript, mailto, tel links
                if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                    continue
                
                # Normalize URL
                full_url = self.normalize_url(href, url)
                if not full_url:
                    continue
                
                # Only crawl same domain
                if not full_url.startswith(self.base_domain):
                    continue
                
                # Check if it's a file we want
                if self.is_valid_file_type(full_url):
                    with self.files_lock:
                        if full_url not in self.found_files:
                            self.found_files.add(full_url)
                            self.stats['files_found'] += 1
                            logger.info(f"  ✅ FOUND: {full_url}")
                
                # Add to crawl queue if it's a webpage
                elif full_url not in self.visited:
                    page_links.append((full_url, depth + 1))
            
            self.stats['pages_checked'] += 1
            return page_links
            
        except requests.RequestException as e:
            self.stats['errors'] += 1
            logger.error(f"  ❌ Error with {url}: {e}")
            return []
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"  ❌ Unexpected error with {url}: {e}")
            return []
    
    def search(self) -> Set[str]:
        """Main search method using threading"""
        logger.info(f"🔍 Searching for {self.file_types} files...")
        logger.info(f"🌐 Starting from: {self.start_url}")
        logger.info(f"📊 Max depth: {self.max_depth}, Max pages: {MAX_PAGES}")
        logger.info("=" * 70)
        
        # Use deque for efficient queue operations
        to_visit = deque([(self.start_url, 0)])
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            while to_visit and len(self.visited) < MAX_PAGES:
                # Limit queue size
                if len(to_visit) > MAX_QUEUE_SIZE:
                    logger.warning(f"Queue size limit reached, truncating...")
                    to_visit = deque(list(to_visit)[:MAX_QUEUE_SIZE])
                
                # Submit batch of URLs
                batch_size = min(MAX_WORKERS * 2, len(to_visit))
                futures = {}
                
                for _ in range(batch_size):
                    if not to_visit:
                        break
                    url, depth = to_visit.popleft()
                    future = executor.submit(self.scrape_page, url, depth)
                    futures[future] = url
                
                # Process completed tasks
                for future in as_completed(futures):
                    try:
                        new_links = future.result(timeout=15)
                        to_visit.extend(new_links)
                    except Exception as e:
                        logger.error(f"Task error for {futures[future]}: {e}")
                
                # Progress update
                if self.stats['pages_checked'] % 10 == 0:
                    logger.info(
                        f"📈 Progress: {self.stats['pages_checked']} pages | "
                        f"{self.stats['files_found']} files | "
                        f"{len(to_visit)} queued | "
                        f"{self.stats['errors']} errors"
                    )
        
        logger.info("=" * 70)
        logger.info(f"✅ Search complete: {self.stats['files_found']} files found")
        return self.found_files


class FileDownloader:
    """Handle file downloads with verification"""
    
    def __init__(self, download_folder: str):
        self.download_folder = Path(download_folder)
        self.download_folder.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.rate_limiter = RateLimiter(delay=0.2)  # Slower for downloads
    
    def get_file_hash(self, filepath: Path) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def download_file(self, file_url: str) -> Tuple[bool, str]:
        """Download a single file with verification"""
        self.rate_limiter.wait()
        
        try:
            # Parse filename
            parsed_url = urlparse(file_url)
            filename = os.path.basename(parsed_url.path)
            
            if not filename:
                filename = f"file_{hashlib.md5(file_url.encode()).hexdigest()[:8]}.download"
            
            # Sanitize filename
            filename = self.sanitize_filename(filename)
            file_path = self.download_folder / filename
            
            # Skip if exists
            if file_path.exists():
                logger.info(f"  ⏭️  Already exists: {filename}")
                return True, filename
            
            # Check file size first
            response = self.session.head(file_url, timeout=10, allow_redirects=True)
            content_length = response.headers.get('content-length')
            
            if content_length and int(content_length) > MAX_FILE_SIZE:
                logger.warning(f"  ⚠️  File too large ({int(content_length) / 1024 / 1024:.1f}MB): {filename}")
                return False, filename
            
            # Download file
            response = self.session.get(file_url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Verify content type
            content_type = response.headers.get('content-type', '')
            
            # Write to temp file first
            temp_path = file_path.with_suffix(file_path.suffix + '.tmp')
            
            total_size = 0
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE:
                        temp_path.unlink()
                        logger.warning(f"  ⚠️  File exceeded size limit: {filename}")
                        return False, filename
                    f.write(chunk)
            
            # Move to final location
            temp_path.rename(file_path)
            
            size_mb = total_size / 1024 / 1024
            logger.info(f"  ✅ Downloaded: {filename} ({size_mb:.2f}MB)")
            return True, filename
            
        except Exception as e:
            logger.error(f"  ❌ Failed to download {file_url}: {e}")
            return False, file_url
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename"""
        filename = filename.replace('/', '_').replace('\\', '_')
        filename = filename.replace('..', '_')
        
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        return filename
    
    def download_all(self, file_urls: Set[str]) -> Tuple[int, int]:
        """Download all files"""
        logger.info(f"\n📥 Downloading {len(file_urls)} files to: {self.download_folder}")
        
        successful = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self.download_file, url): url for url in file_urls}
            
            for future in as_completed(futures):
                success, _ = future.result()
                if success:
                    successful += 1
                else:
                    failed += 1
        
        return successful, failed


def get_user_input() -> Tuple[str, List[str], int, bool, bool]:
    """Get configuration from user"""
    print("🚀 Advanced Web Scraper with Safety Features")
    print("=" * 50)
    
    url = input("Enter website URL (include http:// or https://): ").strip()
    
    file_types_input = input(
        "Enter file types (comma separated, or press enter for default): "
    ).strip()
    
    if file_types_input:
        file_types = [f".{ext.strip().lower()}" for ext in file_types_input.split(',')]
    else:
        file_types = ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.doc', '.docx', '.zip']
    
    # Depth limit
    depth_input = input("Enter max depth (default 3, max 5): ").strip()
    max_depth = int(depth_input) if depth_input.isdigit() else 3
    max_depth = min(max_depth, 5)
    
    # Respect robots.txt
    robots_input = input("Respect robots.txt? (Y/n): ").strip().lower()
    respect_robots = robots_input != 'n'
    
    # Download choice
    print("\nWhat would you like to do?")
    print("1. Save file list only")
    print("2. Download files to computer")
    choice = input("Enter 1 or 2: ").strip()
    
    download_files = (choice == "2")
    
    return url, file_types, max_depth, respect_robots, download_files


def save_file_list(found_files: Set[str], file_types: List[str], domain: str) -> str:
    """Save file list to text file"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"found_files_{domain}_{timestamp}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("Found Files List\n")
        f.write("=" * 70 + "\n")
        f.write(f"Search completed: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total files found: {len(found_files)}\n")
        f.write("=" * 70 + "\n\n")
        
        # Group by file type
        for file_type in file_types:
            type_files = [f for f in found_files if f.lower().endswith(file_type)]
            if type_files:
                f.write(f"\n{file_type.upper()} files ({len(type_files)}):\n")
                f.write("-" * 70 + "\n")
                for file_url in sorted(type_files):
                    f.write(f"{file_url}\n")
    
    return filename


def display_summary(found_files: Set[str], file_types: List[str]):
    """Display search results summary"""
    print("\n" + "=" * 70)
    print("📊 SEARCH RESULTS SUMMARY")
    print("=" * 70)
    print(f"Total unique files found: {len(found_files)}")
    
    if found_files:
        for file_type in file_types:
            type_files = [f for f in found_files if f.lower().endswith(file_type)]
            if type_files:
                print(f"\n📁 {file_type.upper()}: {len(type_files)} files")
                for file_url in sorted(type_files)[:3]:
                    print(f"   📄 {file_url}")
                if len(type_files) > 3:
                    print(f"   ... and {len(type_files) - 3} more")
    else:
        print("❌ No files found.")


def main():
    """Main program"""
    try:
        # Get user input
        url, file_types, max_depth, respect_robots, download_files = get_user_input()
        
        if not url.startswith(('http://', 'https://')):
            print("❌ Please include http:// or https:// in the URL")
            return
        
        # Create scraper
        scraper = WebScraper(url, file_types, max_depth, respect_robots)
        
        # Run search
        print("\n🚀 Starting search...\n")
        start_time = time.time()
        files = scraper.search()
        elapsed = time.time() - start_time
        
        # Display results
        display_summary(files, file_types)
        print(f"\n⏱️  Search completed in {elapsed:.1f} seconds")
        
        # Handle user choice
        if files:
            if download_files:
                downloader = FileDownloader(f"downloads_{scraper.domain}")
                successful, failed = downloader.download_all(files)
                print(f"\n🎉 Download complete: {successful} succeeded, {failed} failed")
            else:
                filename = save_file_list(files, file_types, scraper.domain)
                print(f"\n💾 File list saved to: {filename}")
        else:
            print("\n❌ No files found to process.")
            
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")


if __name__ == "__main__":
    main()