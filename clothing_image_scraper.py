#!/usr/bin/env python3
"""
Clothing Image Scraper Bot
Searches for clothing items using brand, barcode, model, color, and style
Downloads product images to a specified location

Enhanced with:
- Image verification (relevance scoring)
- Perceptual hash duplicate detection
- Exhaustive scraping methods
- Image quality optimization
"""

import os
import re
import json
import requests
from urllib.parse import quote_plus, urljoin, urlparse, unquote, parse_qs, urlencode
from bs4 import BeautifulSoup
import time
from pathlib import Path
import argparse

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False
    print("Warning: openpyxl not installed. Excel reports will not be available.")
    print("Install with: pip install openpyxl")

try:
    from PIL import Image as PILImage
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from scraper_config import (
    CONFIDENCE_THRESHOLD, HASH_SIMILARITY_THRESHOLD, HASH_INDEX_FILE,
    MIN_IMAGE_WIDTH, MIN_IMAGE_HEIGHT, METHOD_TIMEOUT,
    RELIABLE_RETAILERS, URL_SIZE_PATTERNS, HIGHRES_ATTRIBUTES,
    SITE_SPECIFIC_SEARCHES, OCR_ENABLED, OCR_CONFIDENCE_BOOST,
    BROWSER_HEADLESS, BROWSER_TIMEOUT,
)
from image_hash_index import ImageHashIndex


class ClothingImageScraper:
    def __init__(self, download_path="./downloaded_images"):
        """
        Initialize the scraper with a download path

        Args:
            download_path: Directory where images will be saved
        """
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)

        # Rotating user agents to avoid detection
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

        # Enhanced headers to better mimic a real browser
        self.base_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }

        self.session = requests.Session()
        self.current_user_agent_index = 0
        self._update_headers()

        # List of sites known to block automated requests
        self.protected_sites = [
            'macys.com', 'bloomingdales.com', 'neimanmarcus.com',
            'tjmaxx.com', 'marshalls.com', 'nordstrom.com'
        ]

        # Track downloads for reporting
        self.download_report = []

        # Initialize perceptual hash index
        hash_index_path = self.download_path / HASH_INDEX_FILE
        self.hash_index = ImageHashIndex(
            index_file=str(hash_index_path),
            similarity_threshold=HASH_SIMILARITY_THRESHOLD
        )

        # Enhanced reporting stats
        self.method_stats = {}  # method_name -> {attempted, success, fail, time}
        self.verification_stats = {'accepted': 0, 'rejected': 0, 'reasons': []}
        self.duplicate_stats = {'exact': 0, 'perceptual': 0, 'details': []}
        self.quality_stats = {'checked': 0, 'passed': 0, 'failed': 0, 'upgraded': 0}
        self._borderline_urls = {}  # Populated during verification for OCR rescue
        self.captcha_stats = {'detected': 0, 'urls': []}  # CAPTCHA tracking

    def _update_headers(self):
        """Update session headers with a new user agent"""
        headers = self.base_headers.copy()
        headers['User-Agent'] = self.user_agents[self.current_user_agent_index]
        self.session.headers.update(headers)
        # Rotate to next user agent
        self.current_user_agent_index = (self.current_user_agent_index + 1) % len(self.user_agents)

    def _make_request(self, url, timeout=15, retries=2):
        """
        Make a request with anti-detection measures

        Args:
            url: URL to request
            timeout: Request timeout
            retries: Number of retries on failure

        Returns:
            Response object or None
        """
        for attempt in range(retries):
            try:
                # Rotate user agent for each attempt
                self._update_headers()

                # Add referer to make it look like we came from Google
                headers = self.session.headers.copy()
                headers['Referer'] = 'https://www.google.com/'

                # Make request with longer timeout
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=True
                )

                # Check for CAPTCHA before returning
                is_captcha, captcha_type = self._detect_captcha(response)
                if is_captcha:
                    self._log_captcha(url, captcha_type)
                    solved = self._try_solve_captcha(url, captcha_type, response)
                    if solved:
                        return solved
                    # CAPTCHA not solvable — treat as failure
                    if attempt < retries - 1:
                        time.sleep(3)  # Longer delay after CAPTCHA
                        continue
                    return None

                # If successful, return
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    # Try again with different user agent
                    time.sleep(1)
                    continue
                else:
                    response.raise_for_status()

            except requests.exceptions.Timeout:
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                return None
            except requests.exceptions.RequestException:
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                return None

        return None

    def _log_method_stat(self, method_name, success, elapsed):
        """Track per-method statistics."""
        if method_name not in self.method_stats:
            self.method_stats[method_name] = {'attempted': 0, 'success': 0, 'fail': 0, 'total_time': 0.0}
        stats = self.method_stats[method_name]
        stats['attempted'] += 1
        if success:
            stats['success'] += 1
        else:
            stats['fail'] += 1
        stats['total_time'] += elapsed

    # ── CAPTCHA Detection ──────────────────────────────────────────────

    # Common CAPTCHA indicators in page content
    CAPTCHA_SIGNATURES = [
        'captcha', 'recaptcha', 'hcaptcha', 'g-recaptcha',
        'cf-challenge', 'cf-turnstile', 'challenge-platform',
        'please verify you are a human', 'please verify you are not a robot',
        'are you a robot', 'prove you are human', 'human verification',
        'bot detection', 'automated access', 'unusual traffic',
        'sorry, we just need to make sure you\'re not a robot',
        'one more step', 'checking your browser',
        'access denied', 'automated queries',
        'distilcaptchebody',  # Distil Networks
        'px-captcha',  # PerimeterX
        'datadome',  # DataDome
    ]

    def _detect_captcha(self, response):
        """
        Detect if a response contains a CAPTCHA challenge page.

        Checks status codes, headers, and page content for common CAPTCHA indicators.

        Args:
            response: requests.Response object

        Returns:
            Tuple of (is_captcha: bool, captcha_type: str or None)
        """
        if response is None:
            return False, None

        # Check status codes commonly used for CAPTCHA challenges
        if response.status_code in (403, 429, 503):
            # These could be CAPTCHA but also normal blocks — check content
            pass

        content_lower = response.text[:5000].lower() if response.text else ''

        # Check for CAPTCHA signatures in the page content
        for sig in self.CAPTCHA_SIGNATURES:
            if sig in content_lower:
                # Determine CAPTCHA type
                if 'recaptcha' in content_lower or 'g-recaptcha' in content_lower:
                    return True, 'reCAPTCHA'
                elif 'hcaptcha' in content_lower:
                    return True, 'hCaptcha'
                elif 'cf-challenge' in content_lower or 'cf-turnstile' in content_lower:
                    return True, 'Cloudflare'
                elif 'px-captcha' in content_lower:
                    return True, 'PerimeterX'
                elif 'datadome' in content_lower:
                    return True, 'DataDome'
                elif 'distilcaptchebody' in content_lower:
                    return True, 'Distil'
                else:
                    return True, 'generic'

        # Check for very short pages with challenge-like headers
        if response.status_code in (403, 429, 503):
            content_length = len(response.text) if response.text else 0
            if content_length < 2000:
                # Very short error page, likely a block/challenge
                if any(h in response.headers.get('server', '').lower() for h in ['cloudflare', 'ddos-guard']):
                    return True, 'WAF-block'

        return False, None

    def _detect_captcha_in_soup(self, soup):
        """
        Detect CAPTCHA indicators in a parsed BeautifulSoup page.

        Used when we already have a parsed page (e.g., from extract_images_from_page).

        Args:
            soup: BeautifulSoup object

        Returns:
            Tuple of (is_captcha: bool, captcha_type: str or None)
        """
        if soup is None:
            return False, None

        # Check for CAPTCHA-related elements first (most reliable)
        if soup.select_one('.g-recaptcha, [data-sitekey*="recaptcha"]'):
            return True, 'reCAPTCHA'
        if soup.select_one('.h-captcha'):
            return True, 'hCaptcha'
        if soup.select_one('.cf-turnstile'):
            return True, 'Cloudflare'
        if soup.select_one('#px-captcha'):
            return True, 'PerimeterX'
        if soup.select_one('#distilCaptchaForm'):
            return True, 'Distil'
        if soup.select_one('#captcha, .captcha, [data-sitekey]'):
            return True, 'element-detected'

        # Fall back to text-based detection
        page_text = soup.get_text(separator=' ', strip=True)[:5000].lower()
        for sig in self.CAPTCHA_SIGNATURES:
            if sig in page_text:
                if 'recaptcha' in page_text or 'g-recaptcha' in page_text:
                    return True, 'reCAPTCHA'
                elif 'hcaptcha' in page_text:
                    return True, 'hCaptcha'
                elif 'cloudflare' in page_text or 'cf-challenge' in page_text:
                    return True, 'Cloudflare'
                elif 'px-captcha' in page_text:
                    return True, 'PerimeterX'
                elif 'datadome' in page_text:
                    return True, 'DataDome'
                else:
                    return True, 'generic'

        return False, None

    def _log_captcha(self, url, captcha_type):
        """Log a CAPTCHA detection event."""
        self.captcha_stats['detected'] += 1
        self.captcha_stats['urls'].append({
            'url': url,
            'type': captcha_type,
            'timestamp': time.time(),
        })
        print(f"  CAPTCHA detected ({captcha_type}): {url[:80]}...")

    def _try_solve_captcha(self, url, captcha_type, response=None):
        """
        Hook for CAPTCHA solving services.

        Override this method or set self.captcha_solver to integrate a solving service
        (e.g., 2Captcha, Anti-Captcha). By default, logs and skips.

        Args:
            url: The URL that returned a CAPTCHA
            captcha_type: Type of CAPTCHA detected
            response: Original response object (if available)

        Returns:
            Solved response object, or None if not solvable
        """
        solver = getattr(self, 'captcha_solver', None)
        if solver and callable(solver):
            try:
                return solver(url, captcha_type, response)
            except Exception as e:
                print(f"  CAPTCHA solver error: {e}")
        return None

    # ── Image Verification ───────────────────────────────────────────────

    def _verify_image_relevance(self, img_url, source_url, item_data, page_context=None):
        """
        Verify that an image URL is relevant to the item being searched.

        Assigns a confidence score based on identifiers found in the page context,
        image URL, alt text, and surrounding text.

        Args:
            img_url: The candidate image URL
            source_url: The page URL where the image was found
            item_data: Dict with keys brand, model, style, color, barcode
            page_context: Optional dict with 'title', 'alt_text', 'surrounding_text', 'soup'

        Returns:
            Tuple of (score: float, reasons: list of str)
        """
        score = 0.0
        reasons = []

        # Build identifiers list from item data
        identifiers = []
        for key in ('brand', 'model', 'style', 'color', 'barcode'):
            val = item_data.get(key)
            if val:
                identifiers.append(val.lower())

        if not identifiers:
            return 1.0, ['no_identifiers_to_check']

        # Normalize for comparison
        img_url_lower = img_url.lower()
        source_url_lower = source_url.lower() if source_url else ''

        page_title = ''
        alt_text = ''
        surrounding_text = ''
        if page_context:
            page_title = (page_context.get('title') or '').lower()
            alt_text = (page_context.get('alt_text') or '').lower()
            surrounding_text = (page_context.get('surrounding_text') or '').lower()

        # +0.3 if page title or source URL contains brand or model
        for ident in identifiers:
            if ident in page_title or ident in source_url_lower:
                score += 0.3
                reasons.append(f'page_title_or_url_match:{ident}')
                break

        # +0.2 if image alt text contains any identifier
        for ident in identifiers:
            if ident in alt_text:
                score += 0.2
                reasons.append(f'alt_text_match:{ident}')
                break

        # +0.2 if image URL/filename contains any identifier
        for ident in identifiers:
            if ident in img_url_lower:
                score += 0.2
                reasons.append(f'img_url_match:{ident}')
                break

        # +0.2 if surrounding text contains identifiers
        for ident in identifiers:
            if ident in surrounding_text:
                score += 0.2
                reasons.append(f'surrounding_text_match:{ident}')
                break

        # +0.1 if source is a known reliable retailer
        for retailer in RELIABLE_RETAILERS:
            if retailer in source_url_lower or retailer in img_url_lower:
                score += 0.1
                reasons.append(f'reliable_retailer:{retailer}')
                break

        # OCR verification boost (on already-downloaded images, called separately)
        # This is handled in _ocr_verify_image() after download

        return score, reasons

    def _extract_ocr_text(self, filepath):
        """
        Extract text from a downloaded image using OCR.

        Args:
            filepath: Path to the image file

        Returns:
            Extracted text as lowercase string, or empty string on failure
        """
        if not OCR_ENABLED or not TESSERACT_AVAILABLE or not PILLOW_AVAILABLE:
            return ''

        try:
            with PILImage.open(filepath) as img:
                # Convert to RGB if necessary (e.g., RGBA or palette images)
                if img.mode not in ('L', 'RGB'):
                    img = img.convert('RGB')
                text = pytesseract.image_to_string(img, timeout=5)
                return text.lower().strip()
        except Exception:
            # OCR failure should never block scraping
            return ''

    def _ocr_verify_image(self, filepath, item_data):
        """
        Post-download OCR verification: extract text from image and check
        if it matches any item identifiers.

        Args:
            filepath: Path to the downloaded image
            item_data: Dict with brand, model, style, color, barcode

        Returns:
            Tuple of (ocr_boost: float, ocr_text: str, matched_identifiers: list)
        """
        ocr_text = self._extract_ocr_text(filepath)
        if not ocr_text:
            return 0.0, '', []

        identifiers = []
        for key in ('brand', 'model', 'style', 'color', 'barcode'):
            val = item_data.get(key)
            if val:
                identifiers.append(val.lower())

        if not identifiers:
            return 0.0, ocr_text, []

        matched = [ident for ident in identifiers if ident in ocr_text]
        boost = OCR_CONFIDENCE_BOOST if matched else 0.0
        return boost, ocr_text, matched

    # ── Image Quality Optimization ───────────────────────────────────────

    def _upgrade_image_url(self, url):
        """
        Try to upgrade an image URL to a higher-quality version.

        Applies URL manipulation heuristics: remove size suffixes,
        replace path segments, modify query parameters.

        Args:
            url: Original image URL

        Returns:
            Upgraded URL (may be the same as input if no upgrades apply)
        """
        upgraded = url

        # Remove size suffixes from filename
        for suffix in URL_SIZE_PATTERNS['suffixes_to_remove']:
            if suffix in upgraded:
                upgraded = upgraded.replace(suffix, '')

        # Replace path segments
        for old_seg, new_seg in URL_SIZE_PATTERNS['path_replacements'].items():
            if old_seg in upgraded:
                upgraded = upgraded.replace(old_seg, new_seg)

        # Modify query parameters for larger dimensions
        parsed = urlparse(upgraded)
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            changed = False
            for param_name, new_val in URL_SIZE_PATTERNS['param_upgrades'].items():
                if param_name in params:
                    params[param_name] = [new_val]
                    changed = True
            if changed:
                # Rebuild URL with updated params
                flat_params = {k: v[0] for k, v in params.items()}
                new_query = urlencode(flat_params)
                upgraded = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"

        if upgraded != url:
            self.quality_stats['upgraded'] += 1

        return upgraded

    def _extract_highres_from_soup(self, soup, base_url):
        """
        Extract high-resolution image URLs from page using advanced techniques.

        Checks srcset, high-res data attributes, og:image, twitter:image,
        and JSON-LD structured data.

        Args:
            soup: BeautifulSoup object of the page
            base_url: Base URL for resolving relative URLs

        Returns:
            List of high-resolution image URLs
        """
        highres_urls = []

        # Check srcset attributes for highest resolution
        for img in soup.find_all('img', {'srcset': True}):
            srcset = img['srcset']
            candidates = []
            for entry in srcset.split(','):
                parts = entry.strip().split()
                if len(parts) >= 1:
                    candidate_url = parts[0]
                    width = 0
                    if len(parts) >= 2 and parts[1].endswith('w'):
                        try:
                            width = int(parts[1][:-1])
                        except ValueError:
                            pass
                    candidates.append((candidate_url, width))
            if candidates:
                # Pick the largest
                candidates.sort(key=lambda x: x[1], reverse=True)
                best = candidates[0][0]
                if best.startswith('//'):
                    best = 'https:' + best
                elif best.startswith('/'):
                    best = urljoin(base_url, best)
                if best.startswith('http'):
                    highres_urls.append(best)

        # Check high-res data attributes
        for attr in HIGHRES_ATTRIBUTES:
            for tag in soup.find_all(attrs={attr: True}):
                src = tag[attr]
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = urljoin(base_url, src)
                    if src.startswith('http'):
                        highres_urls.append(src)

        # Check og:image and twitter:image meta tags
        for meta in soup.find_all('meta', {'property': 'og:image'}):
            content = meta.get('content')
            if content and content.startswith('http'):
                highres_urls.append(content)
        for meta in soup.find_all('meta', {'name': 'twitter:image'}):
            content = meta.get('content')
            if content and content.startswith('http'):
                highres_urls.append(content)

        # Check JSON-LD structured data for product images
        for script in soup.find_all('script', {'type': 'application/ld+json'}):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        self._extract_jsonld_images(item, highres_urls)
                elif isinstance(data, dict):
                    self._extract_jsonld_images(data, highres_urls)
            except (json.JSONDecodeError, TypeError):
                continue

        return highres_urls

    def _extract_jsonld_images(self, data, results):
        """Extract image URLs from a JSON-LD data object."""
        if not isinstance(data, dict):
            return
        img = data.get('image')
        if img:
            if isinstance(img, str) and img.startswith('http'):
                results.append(img)
            elif isinstance(img, list):
                for i in img:
                    if isinstance(i, str) and i.startswith('http'):
                        results.append(i)
                    elif isinstance(i, dict):
                        url = i.get('url') or i.get('contentUrl')
                        if url and url.startswith('http'):
                            results.append(url)

    def _check_image_quality(self, filepath):
        """
        Check if a downloaded image meets minimum quality requirements.

        Args:
            filepath: Path to the downloaded image

        Returns:
            Tuple of (passes: bool, width: int, height: int)
        """
        self.quality_stats['checked'] += 1
        if not PILLOW_AVAILABLE:
            self.quality_stats['passed'] += 1
            return True, 0, 0

        try:
            with PILImage.open(filepath) as img:
                width, height = img.size
            if width >= MIN_IMAGE_WIDTH and height >= MIN_IMAGE_HEIGHT:
                self.quality_stats['passed'] += 1
                return True, width, height
            else:
                self.quality_stats['failed'] += 1
                print(f"  Warning: Image below minimum quality ({width}x{height} < {MIN_IMAGE_WIDTH}x{MIN_IMAGE_HEIGHT}): {Path(filepath).name}")
                return False, width, height
        except Exception:
            self.quality_stats['passed'] += 1
            return True, 0, 0

    # ── Existing Utility Methods ─────────────────────────────────────────

    def build_search_query(self, brand=None, barcode=None, model=None, color=None, style=None):
        """
        Build a search query from provided parameters

        Args:
            brand: Brand name
            barcode: Product barcode
            model: Model number
            color: Color
            style: Style name

        Returns:
            Formatted search query string
        """
        query_parts = []

        if brand:
            query_parts.append(brand)
        if model:
            query_parts.append(model)
        if style:
            query_parts.append(style)
        if color:
            query_parts.append(color)
        if barcode:
            query_parts.append(barcode)

        return ' '.join(query_parts)

    def build_filename(self, brand=None, barcode=None, model=None, color=None, style=None, image_num=1):
        """
        Build filename from search parameters

        Args:
            brand, barcode, model, color, style: Search parameters
            image_num: Image number for multiple images

        Returns:
            Formatted filename
        """
        filename_parts = []

        if brand:
            filename_parts.append(brand)
        if model:
            filename_parts.append(model)
        if style:
            filename_parts.append(style)
        if color:
            filename_parts.append(color)
        if barcode:
            filename_parts.append(barcode)

        filename = '_'.join(filename_parts)
        # Clean filename - remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = filename.replace(' ', '_')

        return f"{filename} - {image_num}.jpg"

    def search_google_images(self, query):
        """
        Search Google Images for the query

        Args:
            query: Search query string

        Returns:
            List of image URLs
        """
        search_url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch"

        try:
            response = self._make_request(search_url, timeout=10, retries=2)

            if response is None:
                print(f"  Failed to access Google Images")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract image URLs from Google Images
            image_urls = []

            # Method 1: Look for img tags
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src and src.startswith('http'):
                    image_urls.append(src)

            # Method 2: Look for data-src in divs
            for div in soup.find_all('div'):
                data_src = div.get('data-src')
                if data_src and data_src.startswith('http'):
                    image_urls.append(data_src)

            return image_urls[:10]  # Return first 10 URLs

        except Exception as e:
            print(f"Error searching Google Images: {e}")
            return []

    def search_google_shopping(self, query):
        """
        Search Google Shopping for product images
        More reliable than scraping individual retail sites

        Args:
            query: Search query string

        Returns:
            List of image URLs
        """
        # Google Shopping search
        search_url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=shop"

        try:
            response = self._make_request(search_url, timeout=10, retries=2)

            if response is None:
                print(f"  Failed to access Google Shopping")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            image_urls = []

            # Extract product images from Google Shopping
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src and src.startswith('http') and 'google' not in src:
                    image_urls.append(src)

            # Look for higher quality images
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if 'imgurl=' in href:
                    # Extract the actual image URL
                    try:
                        img_url = href.split('imgurl=')[1].split('&')[0]
                        img_url = unquote(img_url)
                        if img_url.startswith('http'):
                            image_urls.append(img_url)
                    except Exception:
                        continue

            return image_urls[:15]  # Return up to 15 URLs

        except Exception as e:
            print(f"Error searching Google Shopping: {e}")
            return []

    def build_optimized_search_queries(self, brand=None, barcode=None, model=None, color=None, style=None):
        """
        Build optimized search queries based on provided parameters
        Following specific rules:
        1. brand + model + color
        2. brand + upc/barcode
        3. brand + style + color

        Args:
            brand, barcode, model, color, style: Search parameters

        Returns:
            List of search query strings
        """
        queries = []

        # Rule 1: Brand + Model + Color
        if brand and model and color:
            queries.append(f"{brand} {model} {color}")
        elif brand and model:
            queries.append(f"{brand} {model}")

        # Rule 2: Brand + UPC/Barcode
        if brand and barcode:
            queries.append(f"{brand} {barcode}")
        elif barcode:
            queries.append(barcode)

        # Rule 3: Brand + Style + Color
        if brand and style and color:
            queries.append(f"{brand} {style} {color}")
        elif brand and style:
            queries.append(f"{brand} {style}")

        # Fallback: Just brand if nothing else
        if not queries and brand:
            queries.append(brand)

        return queries

    def search_specific_retailers(self, query):
        """
        Search specific retailer sites for clothing/shoes
        Prioritizes sites that are more accessible to automated requests

        Args:
            query: Search query string

        Returns:
            List of (retailer_name, search_url) tuples
        """
        urls = []
        encoded_query = quote_plus(query)

        # Most Accessible Shoe Retailers (usually work)
        urls.append(('Zappos', f"https://www.zappos.com/search?term={encoded_query}"))
        urls.append(('DSW', f"https://www.dsw.com/en/us/search?q={encoded_query}"))
        urls.append(('Amazon', f"https://www.amazon.com/s?k={encoded_query}"))
        urls.append(('eBay', f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}"))

        # Department Stores & Fashion Retailers
        urls.append(('Belk', f"https://www.belk.com/search/?q={encoded_query}"))
        urls.append(('Forever 21', f"https://www.forever21.com/us/search?q={encoded_query}"))
        urls.append(('Lord & Taylor', f"https://www.lordandtaylor.com/search?q={encoded_query}"))

        # Luxury Fashion Aggregators & Marketplaces
        urls.append(('ModeSens', f"https://modesens.com/search/?q={encoded_query}"))
        urls.append(('Clothbase', f"https://clothbase.com/search?q={encoded_query}"))
        urls.append(('Editorialist', f"https://editorialist.com/search?q={encoded_query}"))
        urls.append(('Brands Gateway', f"https://brandsgateway.com/search?q={encoded_query}"))
        urls.append(('Hello Luxy', f"https://www.helloluxy.com/search?q={encoded_query}"))
        urls.append(('Banter', f"https://www.banter.com/search?q={encoded_query}"))

        # Additional Luxury/Fashion Shoe Sites
        urls.append(('Level Shoes', f"https://us.levelshoes.com/search?q={encoded_query}"))
        urls.append(('Beyond Style', f"https://www.beyondstyle.us/search?q={encoded_query}"))
        urls.append(('YOOX', f"https://www.yoox.com/us/search?q={encoded_query}"))
        urls.append(('The BS', f"https://www.thebs.com/search?q={encoded_query}"))
        urls.append(('Fetching', f"https://fetching.co.kr/search?q={encoded_query}"))

        # Brand Direct Sites (when brand is detected)
        query_lower = query.lower()
        if 'nike' in query_lower:
            urls.append(('Nike', f"https://www.nike.com/w?q={encoded_query}"))
        if 'adidas' in query_lower:
            urls.append(('Adidas', f"https://www.adidas.com/us/search?q={encoded_query}"))
        if 'puma' in query_lower:
            urls.append(('Puma', f"https://us.puma.com/us/en/search?q={encoded_query}"))
        if 'new balance' in query_lower:
            urls.append(('New Balance', f"https://www.newbalance.com/search/?q={encoded_query}"))
        if 'converse' in query_lower:
            urls.append(('Converse', f"https://www.converse.com/shop?q={encoded_query}"))
        if 'vans' in query_lower:
            urls.append(('Vans', f"https://www.vans.com/shop/search?q={encoded_query}"))
        if 'stuart weitzman' in query_lower:
            urls.append(('Stuart Weitzman', f"https://www.stuartweitzman.com/search/?q={encoded_query}"))
        if 'sam edelman' in query_lower:
            urls.append(('Sam Edelman', f"https://www.samedelman.com/search?q={encoded_query}"))
        if 'steve madden' in query_lower:
            urls.append(('Steve Madden', f"https://www.stevemadden.com/search?q={encoded_query}"))

        # General Accessible Retailers
        urls.append(('Walmart', f"https://www.walmart.com/search?q={encoded_query}"))
        urls.append(('Target', f"https://www.target.com/s?searchTerm={encoded_query}"))
        urls.append(('6pm', f"https://www.6pm.com/search?term={encoded_query}"))

        return urls

    def extract_images_from_page(self, url, retailer_name='generic'):
        """
        Extract product images from various retailer pages.
        Enhanced to also extract high-res images and structured data.

        Args:
            url: Product page URL
            retailer_name: Name of retailer for specialized parsing

        Returns:
            List of image URLs (high-res preferred)
        """
        try:
            # Use enhanced request method
            response = self._make_request(url, timeout=METHOD_TIMEOUT, retries=2)

            if response is None:
                print(f"    Failed to access page: {url}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            # Check for CAPTCHA before extracting images
            is_captcha, captcha_type = self._detect_captcha_in_soup(soup)
            if is_captcha:
                self._log_captcha(url, captcha_type)
                return []

            image_urls = []

            # First, try to get high-res images from structured data / meta tags
            highres = self._extract_highres_from_soup(soup, url)
            image_urls.extend(highres)

            # Retailer-specific extraction methods
            if 'tjmaxx' in url.lower() or 'marshalls' in url.lower():
                image_urls.extend(self._extract_tjx_images(soup, url))
            elif 'nordstrom' in url.lower():
                image_urls.extend(self._extract_nordstrom_images(soup, url))
            elif 'macys' in url.lower():
                image_urls.extend(self._extract_macys_images(soup, url))
            elif 'zappos' in url.lower():
                image_urls.extend(self._extract_zappos_images(soup, url))
            elif 'amazon' in url.lower():
                image_urls.extend(self._extract_amazon_images(soup, url))
            elif 'nike' in url.lower():
                image_urls.extend(self._extract_nike_images(soup, url))
            else:
                # Generic extraction
                image_urls.extend(self._extract_generic_images(soup, url))

            # Try upgrading all URLs to higher quality
            upgraded_urls = []
            for img_url in image_urls:
                upgraded = self._upgrade_image_url(img_url)
                upgraded_urls.append(upgraded)

            # Remove duplicates while preserving order (prefer upgraded/highres first)
            seen = set()
            unique_images = []
            for img_url in upgraded_urls:
                sig = self._create_image_signature(img_url)
                if sig not in seen:
                    seen.add(sig)
                    unique_images.append(img_url)

            return unique_images

        except Exception as e:
            print(f"Error extracting images from {url}: {e}")
            return []

    def _extract_tjx_images(self, soup, base_url):
        """Extract images from TJX sites (TJ Maxx, Marshalls)"""
        images = []

        # Product images
        for img in soup.find_all('img', {'class': re.compile(r'product.*image|slide.*image', re.I)}):
            src = img.get('src') or img.get('data-src')
            if src:
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(base_url, src)
                src = src.replace('_small', '_large').replace('_thumb', '_large')
                images.append(src)

        # Fallback: any product image
        if not images:
            for img in soup.find_all('img'):
                img_class = ' '.join(img.get('class', []))
                if 'product' in img_class.lower():
                    src = img.get('src') or img.get('data-src')
                    if src and src.startswith('http'):
                        images.append(src)

        return images

    def _extract_nordstrom_images(self, soup, base_url):
        """Extract images from Nordstrom"""
        images = []

        # Look for picture elements and high-res images
        for picture in soup.find_all('picture'):
            for source in picture.find_all('source'):
                srcset = source.get('srcset')
                if srcset:
                    # Get highest resolution image
                    urls = [s.strip().split()[0] for s in srcset.split(',')]
                    if urls:
                        images.append(urls[-1])

        # Look for img with data-src
        for img in soup.find_all('img', {'data-src': True}):
            images.append(img['data-src'])

        return images

    def _extract_macys_images(self, soup, base_url):
        """Extract images from Macy's"""
        images = []

        # Macy's uses specific image classes
        for img in soup.find_all('img', {'class': re.compile(r'productImage|mainImage', re.I)}):
            src = img.get('src') or img.get('data-src')
            if src:
                # Upgrade to larger size
                src = src.replace('_fpx.tif', '_fpx.tif?wid=1200')
                images.append(src)

        return images

    def _extract_zappos_images(self, soup, base_url):
        """Extract images from Zappos"""
        images = []

        # Zappos product images
        for img in soup.find_all('img', {'itemprop': 'image'}):
            src = img.get('src')
            if src:
                images.append(src)

        # Alternative: look for data-zoom-image
        for img in soup.find_all('img', {'data-zoom-image': True}):
            images.append(img['data-zoom-image'])

        return images

    def _extract_amazon_images(self, soup, base_url):
        """Extract images from Amazon"""
        images = []

        # Amazon product images
        for img in soup.find_all('img', {'data-old-hires': True}):
            images.append(img['data-old-hires'])

        for img in soup.find_all('img', {'data-a-hires': True}):
            images.append(img['data-a-hires'])

        # Fallback to regular images
        if not images:
            for img in soup.find_all('img', {'class': re.compile(r'product|main', re.I)}):
                src = img.get('src')
                if src and 'images-amazon' in src:
                    images.append(src)

        return images

    def _extract_nike_images(self, soup, base_url):
        """Extract images from Nike"""
        images = []

        # Nike uses picture elements
        for picture in soup.find_all('picture'):
            img = picture.find('img')
            if img:
                src = img.get('src')
                if src:
                    images.append(src)

        return images

    def _extract_generic_images(self, soup, base_url):
        """Generic image extraction for any website"""
        images = []

        # Common product image patterns
        patterns = [
            {'itemprop': 'image'},
            {'class': re.compile(r'product.*image', re.I)},
            {'class': re.compile(r'gallery.*image', re.I)},
            {'class': re.compile(r'zoom.*image', re.I)},
            {'id': re.compile(r'product.*image', re.I)},
        ]

        for pattern in patterns:
            for img in soup.find_all('img', pattern):
                src = img.get('src') or img.get('data-src') or img.get('data-zoom-image')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = urljoin(base_url, src)
                    if src.startswith('http'):
                        images.append(src)

        # If still no images, look for any reasonably sized images
        if not images:
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and src.startswith('http'):
                    # Filter out tiny images (icons, etc.)
                    width = img.get('width')
                    height = img.get('height')
                    if width and height:
                        try:
                            if int(width) > 200 and int(height) > 200:
                                images.append(src)
                        except Exception:
                            images.append(src)
                    else:
                        images.append(src)

        return images

    def search_retailers_for_product(self, query):
        """
        Search multiple retailers and extract product page URLs
        Skips sites that block automated requests

        Args:
            query: Search query

        Returns:
            List of (retailer_name, product_url) tuples
        """
        product_pages = []
        retailer_urls = self.search_specific_retailers(query)

        successful_searches = 0

        # Try Reversible.com with enhanced method first (has heavy bot protection)
        print(f"  Attempting Reversible.com with enhanced method...")
        reversible_results = self._try_reversible_search(query)
        if reversible_results:
            product_pages.extend(reversible_results)
            successful_searches += len(reversible_results)
            print(f"  Found {len(reversible_results)} products on Reversible")
        else:
            print(f"  Reversible blocked or no results (expected - has bot protection)")

        for retailer_name, search_url in retailer_urls:
            try:
                # Skip if we already found enough
                if successful_searches >= 5:
                    break

                # Skip Reversible since we tried it specially above
                if 'reversible' in retailer_name.lower():
                    continue

                print(f"  Searching {retailer_name}...")

                # Use enhanced request method with anti-detection
                response = self._make_request(search_url, timeout=METHOD_TIMEOUT, retries=2)

                if response is None:
                    print(f"  {retailer_name} timed out or failed (skipping)")
                    continue

                # Check for blocking
                if response.status_code == 403:
                    print(f"  {retailer_name} blocked automated access (skipping)")
                    continue

                if response.status_code == 404:
                    continue  # Silently skip 404s

                soup = BeautifulSoup(response.text, 'html.parser')

                # Find product links (common patterns)
                found_product = False
                for a in soup.find_all('a', href=True):
                    href = a['href']

                    # Common product URL patterns
                    if any(keyword in href.lower() for keyword in ['/product/', '/p/', '/item/', '/dp/', '/pd/']):
                        # Make URL absolute
                        if href.startswith('/'):
                            href = urljoin(search_url, href)

                        if href.startswith('http'):
                            product_pages.append((retailer_name, href))
                            found_product = True
                            successful_searches += 1
                            print(f"  Found product on {retailer_name}")
                            break  # Just get first product from each retailer

                if not found_product:
                    print(f"  - No products found on {retailer_name}")

                time.sleep(0.5)  # Be polite

            except requests.exceptions.HTTPError as e:
                if '403' in str(e):
                    print(f"  {retailer_name} blocked automated access (skipping)")
                continue
            except requests.exceptions.Timeout:
                print(f"  {retailer_name} timed out (skipping)")
                continue
            except Exception:
                # Silently skip other errors to keep output clean
                continue

        return product_pages

    def _try_reversible_search(self, query):
        """
        Special method to try accessing Reversible.com with enhanced techniques

        Args:
            query: Search query

        Returns:
            List of (retailer_name, product_url) tuples
        """
        results = []

        try:
            # Use more browser-like headers specifically for Reversible
            enhanced_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'Cache-Control': 'max-age=0',
                'Referer': 'https://www.google.com/'
            }

            # Create a new session just for Reversible
            reversible_session = requests.Session()
            reversible_session.headers.update(enhanced_headers)

            # First, visit the homepage to get cookies
            homepage_url = 'https://www.reversible.com'
            reversible_session.get(homepage_url, timeout=10)
            time.sleep(2)  # Wait like a human would

            # Now try the search
            search_url = f"https://www.reversible.com/search?q={quote_plus(query)}"
            response = reversible_session.get(search_url, timeout=15, allow_redirects=True)

            if response.status_code == 403:
                return []  # Still blocked, return empty

            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for product links on Reversible
            for a in soup.find_all('a', href=True):
                href = a['href']

                # Reversible product URL patterns
                if '/products/' in href or '/items/' in href:
                    if href.startswith('/'):
                        href = urljoin(homepage_url, href)

                    if href.startswith('http'):
                        results.append(('Reversible', href))
                        if len(results) >= 3:  # Get up to 3 products
                            break

            return results

        except Exception:
            # Failed silently
            return []

    # ── Exhaustive Scraping Methods ──────────────────────────────────────

    def _try_structured_data_search(self, queries, image_urls, seen_signatures, search_metadata):
        """
        Method 3: API Discovery - check for JSON-LD structured data and og:image
        on product pages found during earlier scraping stages.
        """
        method_name = 'structured_data'
        start = time.time()
        found = 0

        # Look at product pages we already know about from retailer search
        for query in queries:
            for site in SITE_SPECIFIC_SEARCHES[:3]:  # Limit to top 3 sites
                search_url = f"https://www.google.com/search?q={quote_plus(query + ' ' + site)}"
                try:
                    response = self._make_request(search_url, timeout=METHOD_TIMEOUT, retries=1)
                    if response is None:
                        continue
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Extract product page links from search results
                    for a in soup.find_all('a', href=True):
                        href = a['href']
                        if '/url?q=' in href:
                            try:
                                actual_url = href.split('/url?q=')[1].split('&')[0]
                                actual_url = unquote(actual_url)
                            except Exception:
                                continue
                        else:
                            actual_url = href

                        if not actual_url.startswith('http'):
                            continue
                        if 'google' in actual_url:
                            continue

                        # Try to get structured data from this page
                        page_resp = self._make_request(actual_url, timeout=METHOD_TIMEOUT, retries=1)
                        if page_resp is None:
                            continue
                        page_soup = BeautifulSoup(page_resp.text, 'html.parser')

                        highres = self._extract_highres_from_soup(page_soup, actual_url)
                        for img_url in highres:
                            sig = self._create_image_signature(img_url)
                            if sig not in seen_signatures:
                                image_urls.append(img_url)
                                seen_signatures.add(sig)
                                search_metadata['sources'].append(('Structured Data', actual_url))
                                found += 1

                        if found > 0:
                            break

                    time.sleep(0.5)
                except Exception:
                    continue

                if found > 0:
                    break
            if found > 0:
                break

        elapsed = time.time() - start
        self._log_method_stat(method_name, found > 0, elapsed)
        if found > 0:
            print(f"  Found {found} images via structured data extraction")
        return found

    def _try_site_specific_search(self, queries, image_urls, seen_signatures, search_metadata):
        """
        Method 4: Alternative Sources - try Google with site-specific searches.
        """
        method_name = 'site_specific_search'
        start = time.time()
        found = 0

        for query in queries[:2]:  # Use first 2 queries
            for site_filter in SITE_SPECIFIC_SEARCHES:
                full_query = f"{query} {site_filter}"
                search_url = f"https://www.google.com/search?q={quote_plus(full_query)}&tbm=isch"

                try:
                    response = self._make_request(search_url, timeout=METHOD_TIMEOUT, retries=1)
                    if response is None:
                        continue

                    soup = BeautifulSoup(response.text, 'html.parser')
                    for img in soup.find_all('img'):
                        src = img.get('src') or img.get('data-src')
                        if src and src.startswith('http'):
                            sig = self._create_image_signature(src)
                            if sig not in seen_signatures:
                                image_urls.append(src)
                                seen_signatures.add(sig)
                                search_metadata['sources'].append(('Site-Specific Search', site_filter))
                                found += 1

                    time.sleep(0.5)
                except Exception:
                    continue

                if found >= 3:
                    break
            if found >= 3:
                break

        elapsed = time.time() - start
        self._log_method_stat(method_name, found > 0, elapsed)
        if found > 0:
            print(f"  Found {found} images via site-specific searches")
        return found

    def _try_mobile_amp_endpoints(self, image_urls, seen_signatures, search_metadata):
        """
        Method 5: Mobile/AMP Endpoints - try mobile and AMP versions of found URLs.
        """
        method_name = 'mobile_amp'
        start = time.time()
        found = 0

        # Collect unique source page URLs we've seen
        source_urls = set()
        for source_name, source_url in search_metadata.get('sources', []):
            if source_url and source_url.startswith('http') and 'google' not in source_url:
                source_urls.add(source_url)

        for source_url in list(source_urls)[:3]:  # Limit attempts
            parsed = urlparse(source_url)
            domain = parsed.netloc

            # Try mobile version
            mobile_domain = 'm.' + domain.lstrip('www.')
            mobile_url = f"{parsed.scheme}://{mobile_domain}{parsed.path}"
            if parsed.query:
                mobile_url += f"?{parsed.query}"

            try:
                response = self._make_request(mobile_url, timeout=METHOD_TIMEOUT, retries=1)
                if response and response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    page_images = self._extract_generic_images(soup, mobile_url)
                    for img_url in page_images[:2]:
                        sig = self._create_image_signature(img_url)
                        if sig not in seen_signatures:
                            image_urls.append(img_url)
                            seen_signatures.add(sig)
                            search_metadata['sources'].append(('Mobile Endpoint', mobile_url))
                            found += 1
            except Exception:
                pass

            # Try AMP version
            amp_url = source_url.rstrip('/') + '/amp'
            try:
                response = self._make_request(amp_url, timeout=METHOD_TIMEOUT, retries=1)
                if response and response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    page_images = self._extract_generic_images(soup, amp_url)
                    for img_url in page_images[:2]:
                        sig = self._create_image_signature(img_url)
                        if sig not in seen_signatures:
                            image_urls.append(img_url)
                            seen_signatures.add(sig)
                            search_metadata['sources'].append(('AMP Endpoint', amp_url))
                            found += 1
            except Exception:
                pass

        elapsed = time.time() - start
        self._log_method_stat(method_name, found > 0, elapsed)
        if found > 0:
            print(f"  Found {found} images via mobile/AMP endpoints")
        return found

    def _try_url_pattern_manipulation(self, image_urls, seen_signatures, search_metadata):
        """
        Method 6: URL Pattern Manipulation - for found images, try removing size
        suffixes, modifying dimension params to get higher quality versions.
        """
        method_name = 'url_manipulation'
        start = time.time()
        found = 0

        current_urls = list(image_urls)  # Snapshot
        for img_url in current_urls[:10]:
            upgraded = self._upgrade_image_url(img_url)
            if upgraded != img_url:
                sig = self._create_image_signature(upgraded)
                if sig not in seen_signatures:
                    # Verify the upgraded URL is accessible
                    try:
                        head_resp = self.session.head(upgraded, timeout=5, allow_redirects=True)
                        if head_resp.status_code == 200:
                            content_type = head_resp.headers.get('Content-Type', '')
                            if 'image' in content_type:
                                image_urls.append(upgraded)
                                seen_signatures.add(sig)
                                search_metadata['sources'].append(('URL Manipulation', img_url))
                                found += 1
                    except Exception:
                        pass

        elapsed = time.time() - start
        self._log_method_stat(method_name, found > 0, elapsed)
        if found > 0:
            print(f"  Found {found} upgraded image URLs via URL manipulation")
        return found

    def _try_browser_scraping(self, queries, image_urls, seen_sigs, search_metadata):
        """
        Method 8: Headless browser automation using Playwright.
        Handles JS-rendered content, lazy-loaded images, and infinite scroll.

        Args:
            queries: Search query strings
            image_urls: List to append found image URLs to
            seen_sigs: Set of already-seen image signatures
            search_metadata: Metadata dict to update with sources
        Returns:
            Number of new images found
        """
        method_name = 'browser_automation'
        start = time.time()
        found = 0

        if not PLAYWRIGHT_AVAILABLE:
            print("  Playwright not installed, skipping browser automation")
            self._log_method_stat(method_name, False, time.time() - start)
            return 0

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=BROWSER_HEADLESS)
                context = browser.new_context(
                    user_agent=self.user_agents[0],
                    viewport={'width': 1920, 'height': 1080},
                )
                page = context.new_page()
                page.set_default_timeout(BROWSER_TIMEOUT)

                for query in queries[:2]:  # Limit to first 2 queries
                    if found >= 5:
                        break

                    # Search Google Images with browser
                    search_url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch"
                    try:
                        page.goto(search_url, wait_until='networkidle')
                    except Exception:
                        try:
                            page.goto(search_url, wait_until='domcontentloaded')
                        except Exception:
                            continue

                    # Scroll down to trigger lazy loading
                    for _ in range(3):
                        page.evaluate('window.scrollBy(0, window.innerHeight)')
                        page.wait_for_timeout(500)

                    # Extract image URLs from the rendered page
                    img_elements = page.query_selector_all('img')
                    for img in img_elements:
                        if found >= 5:
                            break
                        try:
                            src = img.get_attribute('src') or ''
                            data_src = img.get_attribute('data-src') or ''
                            img_url = data_src or src

                            if not img_url or not img_url.startswith('http'):
                                continue
                            if 'google' in img_url or 'gstatic' in img_url:
                                continue
                            if any(ext in img_url.lower() for ext in ['.svg', '.gif', '.ico']):
                                continue
                            # Skip tiny images (likely icons)
                            width = img.get_attribute('width')
                            height = img.get_attribute('height')
                            if width and height:
                                try:
                                    if int(width) < 100 or int(height) < 100:
                                        continue
                                except ValueError:
                                    pass

                            sig = self._create_image_signature(img_url)
                            if sig not in seen_sigs:
                                image_urls.append(img_url)
                                seen_sigs.add(sig)
                                search_metadata['sources'].append(('Browser (Google Images)', search_url))
                                found += 1
                        except Exception:
                            continue

                    # Also try visiting product pages found in search results
                    links = page.query_selector_all('a[href]')
                    product_urls = []
                    for link in links[:20]:
                        try:
                            href = link.get_attribute('href') or ''
                            if any(r in href for r in RELIABLE_RETAILERS):
                                product_urls.append(href)
                        except Exception:
                            continue

                    for product_url in product_urls[:3]:
                        if found >= 5:
                            break
                        try:
                            page.goto(product_url, wait_until='networkidle', timeout=BROWSER_TIMEOUT)
                        except Exception:
                            try:
                                page.goto(product_url, wait_until='domcontentloaded', timeout=BROWSER_TIMEOUT)
                            except Exception:
                                continue

                        # Scroll to trigger lazy-loaded product images
                        for _ in range(2):
                            page.evaluate('window.scrollBy(0, window.innerHeight)')
                            page.wait_for_timeout(300)

                        # Extract product images
                        product_imgs = page.query_selector_all('img')
                        for img in product_imgs:
                            if found >= 5:
                                break
                            try:
                                src = img.get_attribute('src') or ''
                                data_src = (img.get_attribute('data-src')
                                           or img.get_attribute('data-zoom-image')
                                           or img.get_attribute('data-highres')
                                           or '')
                                img_url = data_src or src
                                if not img_url or not img_url.startswith('http'):
                                    continue
                                if any(ext in img_url.lower() for ext in ['.svg', '.gif', '.ico']):
                                    continue

                                sig = self._create_image_signature(img_url)
                                if sig not in seen_sigs:
                                    image_urls.append(img_url)
                                    seen_sigs.add(sig)
                                    search_metadata['sources'].append(('Browser (Retailer)', product_url))
                                    found += 1
                            except Exception:
                                continue

                browser.close()

        except Exception as e:
            print(f"  Browser automation error: {e}")

        elapsed = time.time() - start
        self._log_method_stat(method_name, found > 0, elapsed)
        if found > 0:
            print(f"  Found {found} images via browser automation")
        return found

    def _try_scraping_methods(self, queries, max_images, item_data):
        """
        Exhaustive scraping: try methods sequentially, progressing if not enough images.

        Methods attempted in order:
        1. Direct HTTP (Google Shopping + Images) — existing
        2. Retailer Scraping — existing
        3. API Discovery (structured data / JSON-LD)
        4. Alternative Sources (site-specific Google searches)
        5. Mobile/AMP Endpoints
        6. URL Pattern Manipulation
        7. Browser Automation (Playwright headless)

        Args:
            queries: List of search query strings
            max_images: Target number of images
            item_data: Dict with brand, model, style, color, barcode

        Returns:
            Tuple of (image_urls, seen_signatures, search_metadata)
        """
        image_urls = []
        seen_image_signatures = set()
        search_metadata = {
            'search_terms': {
                'brand': item_data.get('brand'),
                'model': item_data.get('model'),
                'style': item_data.get('style'),
                'color': item_data.get('color'),
                'barcode': item_data.get('barcode'),
                'queries': queries,
            },
            'sources': [],
            'image_urls': [],
        }

        print(f"Search queries: {queries}")

        for query in queries:
            print(f"\nSearching: {query}")
            print("=" * 50)

            # ── METHOD 1: Google Shopping ────────────────────────────────
            method_start = time.time()
            print("Method 1: Google Shopping (primary source)...")
            shopping_images = self.search_google_shopping(query)

            for img_url in shopping_images:
                sig = self._create_image_signature(img_url)
                if sig not in seen_image_signatures:
                    image_urls.append(img_url)
                    seen_image_signatures.add(sig)
                    search_metadata['sources'].append(('Google Shopping', f"https://www.google.com/search?q={quote_plus(query)}&tbm=shop"))

            self._log_method_stat('google_shopping', len(shopping_images) > 0, time.time() - method_start)
            print(f"  Found {len(shopping_images)} from Google Shopping (total unique: {len(image_urls)})")

            if len(image_urls) >= max_images:
                print(f"  Found enough images ({len(image_urls)}), stopping search")
                break

            # ── METHOD 2: Google Images ──────────────────────────────────
            method_start = time.time()
            print("Method 2: Google Images...")
            google_images = self.search_google_images(query)

            for img_url in google_images:
                sig = self._create_image_signature(img_url)
                if sig not in seen_image_signatures:
                    image_urls.append(img_url)
                    seen_image_signatures.add(sig)
                    search_metadata['sources'].append(('Google Images', f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch"))

            self._log_method_stat('google_images', len(google_images) > 0, time.time() - method_start)
            print(f"  Found {len(google_images)} from Google Images (total unique: {len(image_urls)})")

            if len(image_urls) >= max_images:
                print(f"  Found enough images ({len(image_urls)}), stopping search")
                break

            # ── METHOD 3: Retailer Scraping ──────────────────────────────
            method_start = time.time()
            print("Method 3: Retail websites...")
            product_pages = self.search_retailers_for_product(query)
            retailer_found = 0

            if product_pages:
                print(f"  Found {len(product_pages)} product pages")
                for retailer_name, product_url in product_pages[:5]:
                    if len(image_urls) >= max_images:
                        break
                    print(f"  Extracting from {retailer_name}...")
                    try:
                        page_images = self.extract_images_from_page(product_url, retailer_name)
                        for img_url in page_images[:3]:
                            sig = self._create_image_signature(img_url)
                            if sig not in seen_image_signatures:
                                image_urls.append(img_url)
                                seen_image_signatures.add(sig)
                                search_metadata['sources'].append((retailer_name, product_url))
                                retailer_found += 1
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"  Error: {e}")
                        continue
            else:
                print("  No retail product pages found")

            self._log_method_stat('retailer_scraping', retailer_found > 0, time.time() - method_start)

            if len(image_urls) >= max_images:
                print(f"  Found enough images ({len(image_urls)}), stopping search")
                break

            time.sleep(1)

        # ── METHOD 4: Structured Data / JSON-LD (if still need more) ────
        if len(image_urls) < max_images:
            print("\nMethod 4: Structured data extraction...")
            self._try_structured_data_search(queries, image_urls, seen_image_signatures, search_metadata)

        # ── METHOD 5: Site-Specific Google Searches ──────────────────────
        if len(image_urls) < max_images:
            print("Method 5: Site-specific searches...")
            self._try_site_specific_search(queries, image_urls, seen_image_signatures, search_metadata)

        # ── METHOD 6: Mobile/AMP Endpoints ───────────────────────────────
        if len(image_urls) < max_images:
            print("Method 6: Mobile/AMP endpoints...")
            self._try_mobile_amp_endpoints(image_urls, seen_image_signatures, search_metadata)

        # ── METHOD 7: URL Pattern Manipulation ───────────────────────────
        if len(image_urls) < max_images:
            print("Method 7: URL pattern manipulation...")
            self._try_url_pattern_manipulation(image_urls, seen_image_signatures, search_metadata)

        # ── METHOD 8: Browser Automation (Headless) ───────────────────────
        if len(image_urls) < max_images and PLAYWRIGHT_AVAILABLE:
            print("Method 8: Browser automation (headless)...")
            self._try_browser_scraping(queries, image_urls, seen_image_signatures, search_metadata)

        return image_urls, seen_image_signatures, search_metadata

    def download_image(self, url, filepath, item_name=""):
        """
        Download an image from URL to filepath.
        Enhanced with perceptual hash duplicate detection and quality checks.

        Args:
            url: Image URL
            filepath: Destination file path
            item_name: Item name for hash index

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.get(url, timeout=15, stream=True)
            response.raise_for_status()

            # Check if it's actually an image
            content_type = response.headers.get('Content-Type', '')
            if 'image' not in content_type:
                print(f"Warning: URL does not appear to be an image: {content_type}")
                return False

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Check for perceptual hash duplicates
            is_dup, original_path, match_type = self.hash_index.is_duplicate(filepath)
            if is_dup:
                print(f"  Duplicate detected ({match_type}): {Path(filepath).name} matches {Path(original_path).name}")
                self.duplicate_stats[match_type if match_type in ('exact', 'perceptual') else 'exact'] += 1
                self.duplicate_stats['details'].append({
                    'new_file': str(filepath),
                    'original_file': original_path,
                    'match_type': match_type,
                })
                # Delete the duplicate
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                return False

            # Add to hash index
            self.hash_index.add_image(filepath, item_name)

            # Post-download quality check
            passes, width, height = self._check_image_quality(filepath)
            if not passes:
                # Keep the image but log the warning (don't delete - it's still useful)
                print(f"  Low quality image kept: {Path(filepath).name} ({width}x{height})")

            print(f"Downloaded: {filepath}")
            return True

        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return False

    def scrape_and_download(self, brand=None, barcode=None, model=None,
                           color=None, style=None, max_images=5,
                           specific_url=None):
        """
        Main method to search for items and download images.
        Enhanced with verification, exhaustive methods, duplicate detection,
        and quality optimization.

        Args:
            brand, barcode, model, color, style: Search parameters
            max_images: Maximum number of images to download
            specific_url: If provided, scrape this specific product URL instead of searching

        Returns:
            Dictionary with downloaded files and metadata
        """
        downloaded_files = []
        item_data = {
            'brand': brand,
            'model': model,
            'style': style,
            'color': color,
            'barcode': barcode,
        }
        item_name = ' '.join(v for v in [brand, model, style] if v)

        if specific_url:
            # Scrape specific URL
            print(f"Scraping specific URL: {specific_url}")

            # Determine retailer from URL
            retailer = 'generic'
            if 'tjmaxx' in specific_url.lower() or 'marshalls' in specific_url.lower():
                retailer = 'tjx'
            elif 'nordstrom' in specific_url.lower():
                retailer = 'nordstrom'
            elif 'macys' in specific_url.lower():
                retailer = 'macys'
            elif 'reversible' in specific_url.lower():
                retailer = 'reversible'

            image_urls = self.extract_images_from_page(specific_url, retailer)
            search_metadata = {
                'search_terms': {},
                'sources': [('Direct URL', specific_url)],
                'image_urls': [],
            }

        else:
            # Build optimized search queries
            queries = self.build_optimized_search_queries(brand, barcode, model, color, style)

            if not queries:
                print("No valid search parameters provided!")
                return {'files': downloaded_files, 'metadata': {'search_terms': {}, 'sources': [], 'image_urls': []}}

            # Use exhaustive scraping methods
            image_urls, seen_sigs, search_metadata = self._try_scraping_methods(queries, max_images, item_data)

        # ── Image Verification ───────────────────────────────────────────
        # Pre-download verification: score each URL based on context.
        # Borderline images (within OCR_CONFIDENCE_BOOST of threshold) are
        # kept as candidates for post-download OCR rescue.
        if image_urls and any(item_data.values()):
            verified_urls = []
            borderline_urls = []  # Could be rescued by OCR
            for img_url in image_urls:
                score, reasons = self._verify_image_relevance(
                    img_url,
                    search_metadata['sources'][0][1] if search_metadata['sources'] else '',
                    item_data
                )
                if score >= CONFIDENCE_THRESHOLD:
                    verified_urls.append(img_url)
                    self.verification_stats['accepted'] += 1
                elif OCR_ENABLED and TESSERACT_AVAILABLE and score >= (CONFIDENCE_THRESHOLD - OCR_CONFIDENCE_BOOST):
                    # Borderline: OCR might push it over threshold
                    borderline_urls.append((img_url, score, reasons))
                else:
                    self.verification_stats['rejected'] += 1
                    self.verification_stats['reasons'].append({
                        'url': img_url,
                        'score': score,
                        'reasons': reasons,
                    })
                    print(f"  Rejected (score={score:.2f}): {img_url[:80]}...")

            if borderline_urls:
                print(f"  {len(borderline_urls)} borderline image(s) pending OCR verification")
            print(f"Verification: {len(verified_urls)} accepted, "
                  f"{len(image_urls) - len(verified_urls) - len(borderline_urls)} rejected, "
                  f"{len(borderline_urls)} borderline")
            image_urls = verified_urls
            # Append borderline URLs at the end for OCR rescue during download
            image_urls.extend(url for url, _, _ in borderline_urls)
            self._borderline_urls = {url: (score, reasons) for url, score, reasons in borderline_urls}

        # Download images
        if not image_urls:
            print("No images found!")
            return {'files': downloaded_files, 'metadata': search_metadata}

        print(f"\nFound {len(image_urls)} verified images")
        print("Downloading images...")

        download_idx = 0
        for img_url in image_urls:
            if len(downloaded_files) >= max_images:
                break

            download_idx += 1
            filename = self.build_filename(brand, barcode, model, color, style, download_idx)
            filepath = self.download_path / filename

            if self.download_image(img_url, filepath, item_name=item_name):
                # Post-download OCR verification for borderline images
                borderline_info = getattr(self, '_borderline_urls', {}).get(img_url)
                if borderline_info is not None:
                    pre_score, pre_reasons = borderline_info
                    ocr_boost, ocr_text, ocr_matches = self._ocr_verify_image(str(filepath), item_data)
                    final_score = pre_score + ocr_boost
                    if final_score >= CONFIDENCE_THRESHOLD:
                        print(f"  OCR rescued (score {pre_score:.2f}+{ocr_boost:.2f}={final_score:.2f}): "
                              f"matched {ocr_matches}")
                        self.verification_stats['accepted'] += 1
                        self.verification_stats.setdefault('ocr_rescued', 0)
                        self.verification_stats['ocr_rescued'] += 1
                    else:
                        # OCR couldn't rescue — remove the file
                        print(f"  OCR could not rescue (score={final_score:.2f}): {img_url[:80]}...")
                        self.verification_stats['rejected'] += 1
                        self.verification_stats['reasons'].append({
                            'url': img_url,
                            'score': final_score,
                            'reasons': pre_reasons + (['ocr_no_match'] if not ocr_matches else []),
                        })
                        try:
                            os.remove(filepath)
                        except OSError:
                            pass
                        # Remove from hash index since we deleted it
                        self.hash_index.remove_image(str(filepath))
                        download_idx -= 1
                        continue
                else:
                    # Non-borderline: run OCR for logging/stats only
                    ocr_boost, ocr_text, ocr_matches = self._ocr_verify_image(str(filepath), item_data)
                    if ocr_matches:
                        self.verification_stats.setdefault('ocr_confirmed', 0)
                        self.verification_stats['ocr_confirmed'] += 1

                downloaded_files.append(str(filepath))
                search_metadata['image_urls'].append(img_url)

            time.sleep(0.5)  # Be polite to servers

        # Add to download report with detailed image info
        report_entry = {
            'brand': brand or '',
            'model': model or '',
            'style': style or '',
            'color': color or '',
            'barcode': barcode or '',
            'url': specific_url or '',
            'success': len(downloaded_files) > 0,
            'num_images': len(downloaded_files),
            'images': [],
        }

        # Add detailed info for each downloaded image
        for idx, filepath in enumerate(downloaded_files):
            img_info = {
                'filename': Path(filepath).name,
                'filepath': str(filepath),
                'image_url': search_metadata['image_urls'][idx] if idx < len(search_metadata['image_urls']) else 'N/A',
                'source_name': search_metadata['sources'][idx][0] if idx < len(search_metadata['sources']) else 'Unknown',
                'source_url': search_metadata['sources'][idx][1] if idx < len(search_metadata['sources']) else 'N/A',
            }
            report_entry['images'].append(img_info)

        self.download_report.append(report_entry)

        return {'files': downloaded_files, 'metadata': search_metadata}

    def _create_image_signature(self, url):
        """
        Create a signature for an image URL to detect duplicates.
        Removes query parameters and focuses on core URL.
        """
        parsed = urlparse(url)
        # Use domain + path as signature (ignore query parameters that might differ)
        signature = f"{parsed.netloc}{parsed.path}"

        # Also check for common image filename patterns
        if '/' in signature:
            filename = signature.split('/')[-1]
            # Remove size/quality parameters from filename
            filename = filename.split('?')[0].split('_')[0]
            signature = f"{parsed.netloc}/{filename}"

        return signature

    def get_run_summary(self):
        """
        Generate a summary report of the current run.

        Returns:
            Dict with verification, duplicate, method, and quality stats
        """
        return {
            'verification': dict(self.verification_stats),
            'duplicates': dict(self.duplicate_stats),
            'methods': dict(self.method_stats),
            'quality': dict(self.quality_stats),
            'captcha': dict(self.captcha_stats),
            'hash_report': self.hash_index.get_duplicate_report(),
        }


def main():
    parser = argparse.ArgumentParser(description='Clothing Image Scraper Bot')
    parser.add_argument('--brand', type=str, help='Brand name')
    parser.add_argument('--barcode', type=str, help='Product barcode')
    parser.add_argument('--model', type=str, help='Model number')
    parser.add_argument('--color', type=str, help='Color')
    parser.add_argument('--style', type=str, help='Style name')
    parser.add_argument('--url', type=str, help='Specific product URL to scrape')
    parser.add_argument('--output', type=str, default='./downloaded_images',
                       help='Output directory for images')
    parser.add_argument('--max-images', type=int, default=5,
                       help='Maximum number of images to download')

    args = parser.parse_args()

    # Create scraper instance
    scraper = ClothingImageScraper(download_path=args.output)

    # Scrape and download
    result = scraper.scrape_and_download(
        brand=args.brand,
        barcode=args.barcode,
        model=args.model,
        color=args.color,
        style=args.style,
        max_images=args.max_images,
        specific_url=args.url
    )

    files = result.get('files', [])
    print(f"\nDownloaded {len(files)} images:")
    for f in files:
        print(f"  - {f}")

    # Print run summary
    summary = scraper.get_run_summary()
    print(f"\n--- Run Summary ---")
    ocr_rescued = summary['verification'].get('ocr_rescued', 0)
    ocr_confirmed = summary['verification'].get('ocr_confirmed', 0)
    print(f"Verification: {summary['verification']['accepted']} accepted, {summary['verification']['rejected']} rejected")
    if ocr_rescued or ocr_confirmed:
        print(f"  OCR: {ocr_rescued} rescued, {ocr_confirmed} confirmed")
    print(f"Duplicates: {summary['duplicates']['exact']} exact, {summary['duplicates']['perceptual']} perceptual")
    print(f"Quality: {summary['quality']['checked']} checked, {summary['quality']['passed']} passed, {summary['quality']['failed']} below threshold")
    captcha_count = summary['captcha']['detected']
    if captcha_count:
        print(f"CAPTCHAs: {captcha_count} detected and skipped")
    print(f"Methods used:")
    for method, stats in summary['methods'].items():
        print(f"  {method}: {stats['attempted']} attempts, {stats['success']} success, {stats['total_time']:.1f}s")


if __name__ == "__main__":
    main()
