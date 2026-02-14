#!/usr/bin/env python3
"""
JSON-based Clothing Image Scraper
Reads search parameters from a JSON file and processes them continuously
"""

import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime
import argparse

# Add current directory to path to import ClothingImageScraper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from clothing_image_scraper import ClothingImageScraper
except ImportError:
    print("ERROR: clothing_image_scraper.py not found in the same directory!")
    print("Please make sure clothing_image_scraper.py is in the same folder as this script.")
    sys.exit(1)


class JSONBatchScraper:
    def __init__(self, json_file, output_dir="./downloaded_images", 
                 delay_between_items=2, log_file=None):
        """
        Initialize JSON batch scraper
        
        Args:
            json_file: Path to JSON file with search parameters
            output_dir: Directory to save downloaded images
            delay_between_items: Seconds to wait between processing items
            log_file: Optional log file path
        """
        self.json_file = Path(json_file)
        self.output_dir = Path(output_dir)
        self.delay_between_items = delay_between_items
        self.log_file = Path(log_file) if log_file else None
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize scraper
        self.scraper = ClothingImageScraper(download_path=str(self.output_dir))
        
        # Statistics
        self.stats = {
            'total_items': 0,
            'successful': 0,
            'failed': 0,
            'total_images': 0,
            'start_time': None,
            'end_time': None
        }
    
    def log(self, message, level='INFO'):
        """Log a message to console and optionally to file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}"
        
        print(log_message)
        
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_message + '\n')
    
    def read_json_items(self):
        """
        Read items from JSON file
        
        Returns:
            List of dictionaries containing search parameters
        """
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Support both array format and object format
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and 'items' in data:
                items = data['items']
            else:
                self.log("JSON must be an array or have an 'items' key", 'ERROR')
                return []
            
            # Validate items
            valid_items = []
            search_params = ['brand', 'barcode', 'model', 'color', 'style', 'url']
            
            for idx, item in enumerate(items, start=1):
                if any(param in item for param in search_params):
                    item['item_number'] = idx
                    valid_items.append(item)
                else:
                    self.log(f"Item {idx}: Skipping - no search parameters", 'WARNING')
            
            self.log(f"Loaded {len(valid_items)} valid items from JSON", 'SUCCESS')
            return valid_items
            
        except FileNotFoundError:
            self.log(f"JSON file not found: {self.json_file}", 'ERROR')
            return []
        except json.JSONDecodeError as e:
            self.log(f"Invalid JSON format: {e}", 'ERROR')
            return []
        except Exception as e:
            self.log(f"Error reading JSON: {e}", 'ERROR')
            return []
    
    def process_item(self, item, item_num):
        """Process a single item from JSON"""
        item_id = item.get('item_number', '?')
        
        # Extract parameters
        brand = item.get('brand')
        barcode = item.get('barcode')
        model = item.get('model')
        color = item.get('color')
        style = item.get('style')
        url = item.get('url')
        max_images = int(item.get('max_images', 5))
        notes = item.get('notes', '')
        
        # Build display name
        display_parts = []
        if brand:
            display_parts.append(brand)
        if model:
            display_parts.append(model)
        if style:
            display_parts.append(style)
        display_name = ' '.join(display_parts) if display_parts else f"Item {item_id}"
        
        self.log("="*70, 'INFO')
        self.log(f"Processing Item {item_num}/{self.stats['total_items']}: {display_name}", 'INFO')
        if notes:
            self.log(f"Notes: {notes}", 'INFO')
        
        try:
            files = self.scraper.scrape_and_download(
                brand=brand,
                barcode=barcode,
                model=model,
                color=color,
                style=style,
                specific_url=url,
                max_images=max_images
            )
            
            num_images = len(files)
            
            if num_images > 0:
                self.log(f"✓ Success! Downloaded {num_images} images", 'SUCCESS')
                for f in files:
                    self.log(f"  • {Path(f).name}", 'INFO')
                self.stats['successful'] += 1
                self.stats['total_images'] += num_images
            else:
                self.log(f"✗ No images found", 'WARNING')
                self.stats['failed'] += 1
            
            return num_images
            
        except Exception as e:
            self.log(f"✗ Error: {e}", 'ERROR')
            self.stats['failed'] += 1
            return 0
    
    def run(self):
        """Main method to process all items from JSON"""
        self.log("="*70, 'INFO')
        self.log("JSON Batch Scraper Starting", 'INFO')
        self.log(f"JSON File: {self.json_file}", 'INFO')
        self.log(f"Output Directory: {self.output_dir}", 'INFO')
        self.log("="*70, 'INFO')
        
        # Read items
        items = self.read_json_items()
        
        if not items:
            self.log("No items to process", 'WARNING')
            return
        
        # Initialize stats
        self.stats['total_items'] = len(items)
        self.stats['start_time'] = datetime.now()
        
        # Process each item
        for idx, item in enumerate(items, start=1):
            self.process_item(item, idx)
            
            if idx < len(items):
                self.log(f"Waiting {self.delay_between_items} seconds before next item...", 'INFO')
                time.sleep(self.delay_between_items)
        
        # Finalize stats
        self.stats['end_time'] = datetime.now()
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        # Print summary
        self.log("="*70, 'INFO')
        self.log("BATCH PROCESSING COMPLETE", 'SUCCESS')
        self.log("="*70, 'INFO')
        self.log(f"Total Items Processed: {self.stats['total_items']}", 'INFO')
        self.log(f"Successful: {self.stats['successful']}", 'SUCCESS')
        self.log(f"Failed: {self.stats['failed']}", 'ERROR' if self.stats['failed'] > 0 else 'INFO')
        self.log(f"Total Images Downloaded: {self.stats['total_images']}", 'SUCCESS')
        self.log(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)", 'INFO')
        self.log(f"Average: {duration/self.stats['total_items']:.1f} seconds per item", 'INFO')
        self.log("="*70, 'INFO')


def create_sample_json(filename="items.json"):
    """Create a sample JSON file with example data"""
    sample_data = {
        "items": [
            {
                "brand": "stuart weitzman",
                "model": "SD166",
                "style": "GEMCUT 85 SANDAL",
                "max_images": 5,
                "notes": "Example from original request"
            },
            {
                "brand": "Nike",
                "model": "Air Max 270",
                "style": "Running Shoe",
                "color": "Black",
                "max_images": 3,
                "notes": "Popular running shoe"
            },
            {
                "brand": "Adidas",
                "style": "Ultraboost",
                "color": "White",
                "max_images": 4
            },
            {
                "url": "https://tjmaxx.tjx.com/store/jump/product/Made-In-Spain-Suede-Gemcut-85-Heeled-Sandals/1001136525",
                "max_images": 5,
                "notes": "Using direct URL"
            }
        ]
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f, indent=2)
    
    print(f"Sample JSON created: {filename}")
    print(f"Edit this file and add your items, then run:")
    print(f"  python json_scraper.py {filename}")


def main():
    parser = argparse.ArgumentParser(
        description='JSON-based Clothing Image Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process items from JSON file
  python json_scraper.py items.json
  
  # Custom output directory
  python json_scraper.py items.json --output ./my_images
  
  # Create sample JSON file
  python json_scraper.py --create-sample items.json
  
  # Process with custom delay and logging
  python json_scraper.py items.json --delay 5 --log scraper.log

JSON Format (Array):
  [
    {
      "brand": "Nike",
      "model": "Air Max",
      "style": "Running",
      "color": "Black",
      "barcode": "",
      "url": "",
      "max_images": 5,
      "notes": "Optional notes"
    }
  ]

JSON Format (Object with items key):
  {
    "items": [
      { ... },
      { ... }
    ]
  }
        """
    )
    
    parser.add_argument('json_file', nargs='?', help='Path to JSON file with search parameters')
    parser.add_argument('--output', type=str, default='./downloaded_images',
                       help='Output directory for images (default: ./downloaded_images)')
    parser.add_argument('--delay', type=int, default=2,
                       help='Delay between items in seconds (default: 2)')
    parser.add_argument('--log', type=str, help='Log file path (optional)')
    parser.add_argument('--create-sample', metavar='FILENAME',
                       help='Create a sample JSON file and exit')
    
    args = parser.parse_args()
    
    if args.create_sample:
        create_sample_json(args.create_sample)
        return
    
    if not args.json_file:
        parser.print_help()
        print("\nError: json_file is required (or use --create-sample)")
        return
    
    scraper = JSONBatchScraper(
        json_file=args.json_file,
        output_dir=args.output,
        delay_between_items=args.delay,
        log_file=args.log
    )
    
    scraper.run()


if __name__ == "__main__":
    main()
