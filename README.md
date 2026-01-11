# 🕷️ Web Scraper

A powerful, safe, and respectful web scraper that discovers and downloads files from websites with built-in safety features and ethical crawling practices.

## ✨ Features

### Core Functionality
- 🔍 **Intelligent Crawling** - Recursively searches websites for specific file types
- 📥 **Batch Downloads** - Download all found files or save URLs to a text file
- 🎯 **Customizable** - Search for any file type you need
- 🧵 **Multi-threaded** - Fast concurrent processing with configurable workers

### Safety & Ethics
- 🤖 **robots.txt Compliance** - Respects website crawling rules
- ⏱️ **Rate Limiting** - Prevents overwhelming servers with requests
- 📊 **Size Limits** - Won't download files over 100MB
- 🔒 **Security** - Filename sanitization prevents directory traversal attacks
- 🛡️ **Content Verification** - Validates file types by content, not just extension

### User Experience
- 📝 **Detailed Logging** - Tracks progress to both console and log file
- 📈 **Real-time Statistics** - Monitor pages checked, files found, and errors
- 🎨 **Clean Output** - Organized reports grouped by file type
- ⚡ **Resume Support** - Skips already downloaded files automatically

## 📋 Requirements

```bash
pip install requests beautifulsoup4 lxml
```

### Dependencies
- `requests` - HTTP library for making web requests
- `beautifulsoup4` - HTML parsing and link extraction
- `lxml` - Fast XML/HTML parser (optional but recommended)

## 🚀 Quick Start

### Basic Usage

1. **Run the script:**
   ```bash
   python scraper.py
   ```

2. **Enter the website URL:**
   ```
   Enter website URL (include http:// or https://): https://example.com
   ```

3. **Choose file types** (or press Enter for defaults):
   ```
   Enter file types (comma separated, or press enter for default): pdf, docx, zip
   ```

4. **Set crawling depth** (how many links deep to follow):
   ```
   Enter max depth (default 3, max 5): 3
   ```

5. **Respect robots.txt:**
   ```
   Respect robots.txt? (Y/n): Y
   ```

6. **Choose action:**
   ```
   What would you like to do?
   1. Save file list only
   2. Download files to computer
   Enter 1 or 2: 2
   ```

## 📖 Usage Examples

### Example 1: Research Paper Collection
```
URL: https://research.university.edu
File types: pdf, doc, docx
Max depth: 2
Action: Download files
```
Output: Downloads all PDFs and documents to `downloads_research.university.edu/`

### Example 2: Image Gallery
```
URL: https://gallery.example.com
File types: jpg, png, gif
Max depth: 1
Action: Download files
```
Output: Downloads all images to `downloads_gallery.example.com/`

### Example 3: Archive Discovery
```
URL: https://archive.org/details/something
File types: zip, tar, gz
Max depth: 2
Action: Save file list only
```
Output: Creates text file `found_files_archive.org_20240115_143022.txt` with all archive URLs

## ⚙️ Configuration

### Default File Types
If you press Enter without specifying file types, these are searched by default:
- `.pdf` - PDF documents
- `.png`, `.jpg`, `.jpeg`, `.gif` - Images
- `.doc`, `.docx` - Microsoft Word documents
- `.zip` - Compressed archives

### Customizable Constants
Edit these in the script to adjust behavior:

```python
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB max per file
MAX_PAGES = 500                     # Stop after checking 500 pages
MAX_QUEUE_SIZE = 1000               # Maximum URLs to queue
REQUEST_DELAY = 0.1                 # Seconds between requests
MAX_WORKERS = 5                     # Concurrent threads
```

## 📁 Output Structure

### Downloaded Files
```
downloads_example.com/
├── document1.pdf
├── image1.png
├── archive.zip
└── report.docx
```

### File List (Text File)
```
Found Files List
======================================================================
Search completed: 2024-01-15 14:30:22
Total files found: 47
======================================================================

.PDF files (15):
----------------------------------------------------------------------
https://example.com/docs/report.pdf
https://example.com/papers/research.pdf
...

.PNG files (32):
----------------------------------------------------------------------
https://example.com/images/logo.png
https://example.com/gallery/photo1.png
...
```

### Log File
A `scraper.log` file is automatically created with detailed information:
```
2024-01-15 14:30:15 - INFO - 🔍 Searching for ['.pdf', '.docx'] files...
2024-01-15 14:30:16 - INFO - ✓ Loaded robots.txt from https://example.com/robots.txt
2024-01-15 14:30:20 - INFO - 📈 Progress: 10 pages | 5 files | 15 queued | 0 errors
```

## 🛡️ Safety Features

### Respects Website Rules
- Checks `robots.txt` before crawling
- Configurable option to ignore robots.txt if needed (use responsibly)

### Rate Limiting
- Automatic delays between requests (default: 0.1 seconds)
- Prevents server overload
- Slower rate for downloads (0.2 seconds)

### File Size Protection
- Checks file size via HEAD request before downloading
- Streams large files in chunks
- Abandons downloads that exceed size limit

### Security Measures
- Sanitizes filenames to prevent path traversal
- Validates URLs to prevent leaving target domain
- Content-type verification for downloaded files

### Memory Management
- Limited queue size prevents memory exhaustion
- Maximum page limit prevents infinite crawling
- Efficient deque-based URL queue

## 📊 Statistics & Monitoring

The scraper provides real-time feedback:
- **Pages checked** - How many pages have been crawled
- **Files found** - Total unique files discovered
- **Queue depth** - URLs waiting to be processed
- **Error count** - Failed requests or downloads
- **Execution time** - Total time taken

## 🔧 Troubleshooting

### Common Issues

**"Could not load robots.txt"**
- Website may not have robots.txt (this is fine)
- Network connectivity issues
- The scraper will continue anyway

**"File too large"**
- File exceeds 100MB limit
- Increase `MAX_FILE_SIZE` if needed
- Or download the URL manually

**"Content type mismatch"**
- File extension doesn't match actual content
- Server may be misconfigured
- File is skipped for safety

**"Reached safety limit"**
- Hit the maximum page limit (default: 500)
- Increase `MAX_PAGES` if needed
- Or reduce `max_depth` for more focused crawling

**"Connection timeout"**
- Server is slow or unresponsive
- Increase timeout values in the code
- Check your internet connection

## ⚠️ Legal & Ethical Considerations

### Before Using This Tool

1. **Check Terms of Service** - Ensure the website allows automated access
2. **Respect robots.txt** - Keep this enabled unless you have permission
3. **Rate Limiting** - Don't disable delays; they protect servers
4. **Copyright** - Downloaded content may be copyrighted
5. **Personal Use** - This tool is for personal research and backup purposes

### Prohibited Uses
- ❌ Scraping websites that explicitly forbid it
- ❌ Overloading servers by removing rate limits
- ❌ Downloading copyrighted content for redistribution
- ❌ Bypassing paywalls or authentication
- ❌ Any illegal or unethical data collection

## 🤝 Contributing

Suggestions for improvements:
- Additional file format support
- Resume capability for interrupted sessions
- GUI interface
- Proxy support
- Authentication handling
- Sitemap.xml parsing
- Better duplicate detection

## 📝 License

This is free and open-source software. Use responsibly and ethically.

## 🆘 Support

If you encounter issues:
1. Check the `scraper.log` file for detailed error messages
2. Verify your internet connection
3. Ensure the target website is accessible
4. Try reducing `MAX_WORKERS` or increasing delays
5. Test with a smaller `max_depth` first

## 🔄 Version History

### v2.0 (Current)
- Added robots.txt compliance
- Implemented rate limiting
- File size verification
- Content-type validation
- Security improvements
- Comprehensive logging
- Better error handling

### v1.0 (Original)
- Basic crawling functionality
- Multi-threaded downloads
- Simple file discovery

---

**Happy Scraping! 🎉** Remember to use this tool responsibly and respect website owners' resources.
