#!/usr/bin/env python3
"""
Example batch processing script for multiple clothing items
"""

import sys
import os
import time

# Add current directory to path to import ClothingImageScraper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from clothing_image_scraper import ClothingImageScraper
except ImportError:
    print("ERROR: clothing_image_scraper.py not found in the same directory!")
    print("Please make sure clothing_image_scraper.py is in the same folder as this script.")
    sys.exit(1)

# Define your items to scrape
items_to_scrape = [
    {
        "brand": "stuart weitzman",
        "model": "SD166",
        "style": "GEMCUT 85 SANDAL",
        "max_images": 5
    },
    {
        "brand": "Nike",
        "model": "Air Max 270",
        "style": "Running Shoe",
        "color": "Black",
        "max_images": 3
    },
    {
        "brand": "Adidas",
        "style": "Ultraboost",
        "color": "White",
        "max_images": 4
    },
    # Add more items as needed
]

def batch_scrape():
    """Process all items in the batch"""
    scraper = ClothingImageScraper(download_path="./batch_downloads")
    
    total_downloaded = 0
    
    for idx, item in enumerate(items_to_scrape, 1):
        print(f"\n{'='*60}")
        print(f"Processing item {idx}/{len(items_to_scrape)}")
        print(f"{'='*60}")
        
        # Extract max_images parameter
        max_images = item.pop('max_images', 5)
        
        try:
            files = scraper.scrape_and_download(**item, max_images=max_images)
            total_downloaded += len(files)
            
            print(f"✓ Downloaded {len(files)} images for this item")
            
        except Exception as e:
            print(f"✗ Error processing item: {e}")
        
        # Be polite - wait between items
        if idx < len(items_to_scrape):
            print("\nWaiting before next item...")
            time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"Batch processing complete!")
    print(f"Total images downloaded: {total_downloaded}")
    print(f"{'='*60}")

if __name__ == "__main__":
    batch_scrape()
