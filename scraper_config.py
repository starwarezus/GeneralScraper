"""
Scraper Configuration
Central configuration file for all tunable parameters
"""

# Image Verification
CONFIDENCE_THRESHOLD = 0.3  # Minimum verification confidence score (0.0 to 1.0)
OCR_ENABLED = True          # Enable OCR text extraction for image verification
OCR_CONFIDENCE_BOOST = 0.15 # Score boost when OCR text matches identifiers

# Perceptual Hashing / Duplicate Prevention
HASH_SIMILARITY_THRESHOLD = 10  # Hamming distance threshold for perceptual hash comparison
HASH_INDEX_FILE = "image_hashes.json"  # Persistent hash index file path

# Image Quality
MIN_IMAGE_WIDTH = 500   # Minimum acceptable image width in pixels
MIN_IMAGE_HEIGHT = 500  # Minimum acceptable image height in pixels

# Timeouts
METHOD_TIMEOUT = 15  # Per-method timeout in seconds

# Browser Automation
BROWSER_HEADLESS = True     # Run browser in headless mode (no visible window)
BROWSER_TIMEOUT = 30000     # Playwright page timeout in milliseconds

# Known reliable retailers for verification scoring
RELIABLE_RETAILERS = [
    'zappos.com', 'nordstrom.com', 'macys.com', 'amazon.com',
    'nike.com', 'adidas.com', 'dsw.com', 'newbalance.com',
    'puma.com', 'converse.com', 'vans.com', 'walmart.com',
    'target.com', '6pm.com', 'stuartweitzman.com', 'samedelman.com',
    'stevemadden.com', 'ebay.com',
]

# URL patterns to strip/replace for image quality upgrades
URL_SIZE_PATTERNS = {
    'suffixes_to_remove': [
        '_thumb', '_small', '_tiny', '_mini', '_xs', '_sm', '_med',
        '_150x150', '_200x200', '_300x300', '_100x100', '_64x64',
        '_thumbnail', '_preview', '_low', '_lowres',
    ],
    'path_replacements': {
        '/thumbnail/': '/original/',
        '/thumbnails/': '/originals/',
        '/preview/': '/full/',
        '/small/': '/large/',
        '/medium/': '/large/',
        '/thumbs/': '/images/',
    },
    'param_upgrades': {
        'width': '1200',
        'w': '1200',
        'wid': '1200',
        'size': 'large',
        'quality': '100',
        'q': '100',
    },
}

# High-res image attributes to check in HTML
HIGHRES_ATTRIBUTES = [
    'data-full', 'data-zoom', 'data-highres', 'data-zoom-image',
    'data-large', 'data-original', 'data-hi-res', 'data-full-size',
    'data-old-hires', 'data-a-hires', 'data-src-zoom',
]

# Site-specific search patterns for exhaustive scraping
SITE_SPECIFIC_SEARCHES = [
    'site:amazon.com',
    'site:ebay.com',
    'site:zappos.com',
    'site:nordstrom.com',
    'site:dsw.com',
]
