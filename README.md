# Clothing Image Scraper Bot

A Python-based web scraping tool for downloading product images of clothing items using brand, barcode, model, color, and style information.

## Features

- Search for clothing items using multiple criteria (brand, model, style, color, barcode)
- Download product images automatically
- Intelligent filename generation based on search parameters
- Support for specific product URLs
- Configurable download location and image count
- Polite scraping with delays to avoid overwhelming servers

## Installation

1. Make sure you have Python 3.7+ installed

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install requests beautifulsoup4 lxml
```

## Usage

### Command Line Interface

#### Basic Example (Your Stuart Weitzman Example)
```bash
python clothing_image_scraper.py \
    --brand "stuart weitzman" \
    --model "SD166" \
    --style "GEMCUT 85 SANDAL"
```

This will:
- Search for images matching the criteria
- Download up to 5 images (default)
- Save them as: `stuart_weitzman_SD166_GEMCUT_85_SANDAL - 1.jpg`, etc.
- Store in `./downloaded_images/` directory

#### Using a Specific URL
```bash
python clothing_image_scraper.py \
    --url "https://tjmaxx.tjx.com/store/jump/product/Made-In-Spain-Suede-Gemcut-85-Heeled-Sandals/1001136525"
```

#### All Parameters
```bash
python clothing_image_scraper.py \
    --brand "Nike" \
    --model "Air Max 270" \
    --style "Running Shoe" \
    --color "Black" \
    --barcode "123456789" \
    --output "./my_images" \
    --max-images 10
```

### Python API

You can also use the scraper programmatically:

```python
from clothing_image_scraper import ClothingImageScraper

# Create scraper instance
scraper = ClothingImageScraper(download_path="./my_images")

# Scrape using search parameters
files = scraper.scrape_and_download(
    brand="stuart weitzman",
    model="SD166",
    style="GEMCUT 85 SANDAL",
    max_images=5
)

print(f"Downloaded {len(files)} images")
for file in files:
    print(file)
```

#### Scraping a Specific URL
```python
scraper = ClothingImageScraper(download_path="./images")

files = scraper.scrape_and_download(
    brand="stuart weitzman",
    model="SD166",
    style="GEMCUT 85 SANDAL",
    specific_url="https://tjmaxx.tjx.com/store/jump/product/Made-In-Spain-Suede-Gemcut-85-Heeled-Sandals/1001136525",
    max_images=10
)
```

## Command Line Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--brand` | Brand name | Optional |
| `--barcode` | Product barcode | Optional |
| `--model` | Model number | Optional |
| `--color` | Color | Optional |
| `--style` | Style name | Optional |
| `--url` | Specific product URL to scrape | Optional |
| `--output` | Output directory for images (default: `./downloaded_images`) | Optional |
| `--max-images` | Maximum number of images to download (default: 5) | Optional |

**Note:** At least one search parameter (brand, barcode, model, color, style) OR a URL must be provided.

## Filename Convention

Images are automatically named using this pattern:
```
{brand}_{model}_{style}_{color}_{barcode} - {number}.jpg
```

Example: `stuart_weitzman_SD166_GEMCUT_85_SANDAL - 1.jpg`

- Spaces are replaced with underscores
- Invalid filename characters are removed
- Images are numbered sequentially

## Examples

### Example 1: Search by Brand and Style
```bash
python clothing_image_scraper.py \
    --brand "Adidas" \
    --style "Ultraboost"
```

Output files:
- `Adidas_Ultraboost - 1.jpg`
- `Adidas_Ultraboost - 2.jpg`
- etc.

### Example 2: Search with Color
```bash
python clothing_image_scraper.py \
    --brand "Levi's" \
    --model "501" \
    --color "Blue" \
    --max-images 3
```

Output files:
- `Levi's_501_Blue - 1.jpg`
- `Levi's_501_Blue - 2.jpg`
- `Levi's_501_Blue - 3.jpg`

### Example 3: Custom Output Directory
```bash
python clothing_image_scraper.py \
    --brand "Gucci" \
    --style "Loafers" \
    --output "/path/to/my/images" \
    --max-images 10
```

### Example 4: Using Barcode
```bash
python clothing_image_scraper.py \
    --barcode "889436589745" \
    --max-images 5
```

## Important Notes

### Web Scraping Ethics
- This tool implements polite scraping with delays between requests
- Respects robots.txt when possible
- Uses appropriate user-agent headers
- Should only be used for legitimate purposes (personal use, research, etc.)

### Limitations
- Some websites may block automated scraping
- Image availability depends on search results
- Some retailers may require authentication
- Dynamic content loaded with JavaScript may not be captured

### Legal Considerations
- Always check the website's Terms of Service before scraping
- Respect copyright on downloaded images
- Use scraped images only for permitted purposes
- Consider rate limiting and server load

## Troubleshooting

### No images found
- Try different search parameters
- Verify the product exists online
- Try using a specific URL instead of search parameters

### Download failures
- Check your internet connection
- Some sites may block automated downloads
- Try reducing `--max-images` value

### Permission errors
- Ensure the output directory is writable
- Try using an absolute path for `--output`

## Advanced Usage

### Batch Processing
Create a script to process multiple items:

```python
from clothing_image_scraper import ClothingImageScraper

items = [
    {"brand": "Nike", "model": "Air Max", "style": "Running"},
    {"brand": "Adidas", "model": "Ultraboost", "color": "White"},
    {"brand": "Puma", "style": "Sneakers"}
]

scraper = ClothingImageScraper(download_path="./batch_images")

for item in items:
    print(f"Processing: {item}")
    files = scraper.scrape_and_download(**item, max_images=3)
    print(f"Downloaded {len(files)} images\n")
```

## Contributing

Feel free to enhance this scraper with:
- Additional retailer-specific extractors
- Better image quality detection
- Duplicate image removal
- Image format conversion
- Metadata extraction

## License

This tool is for educational and personal use. Always respect website terms of service and copyright laws.
