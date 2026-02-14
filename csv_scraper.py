#!/usr/bin/env python3
"""
CSV-based Clothing Image Scraper
Reads search parameters from a CSV file and processes them continuously
"""

import csv
import os
import sys
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


class CSVBatchScraper:
    def __init__(self, csv_file, output_dir="./downloaded_images", 
                 delay_between_items=2, log_file=None):
        """
        Initialize CSV batch scraper
        
        Args:
            csv_file: Path to CSV file with search parameters
            output_dir: Directory to save downloaded images
            delay_between_items: Seconds to wait between processing items
            log_file: Optional log file path
        """
        self.csv_file = Path(csv_file)
        self.output_dir = Path(output_dir)
        self.delay_between_items = delay_between_items
        
        # Create both full log and success-only log
        if log_file:
            self.log_file = Path(log_file)
            # Create success-only log in same directory
            success_log_name = self.log_file.stem + "_SUCCESS_ONLY" + self.log_file.suffix
            self.success_log_file = self.log_file.parent / success_log_name
        else:
            # Default log file names
            self.log_file = self.output_dir / "scraper.log"
            self.success_log_file = self.output_dir / "scraper_SUCCESS_ONLY.log"
        
        # Clear old success log
        if self.success_log_file.exists():
            self.success_log_file.unlink()
        
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
        
        # Collect results for Excel report
        self.report_data = []
    
    def log(self, message, level='INFO', success_only=False):
        """
        Log a message to console and optionally to file
        
        Args:
            message: Message to log
            level: Log level (INFO, SUCCESS, ERROR, WARNING)
            success_only: If True, only log SUCCESS messages to file
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}"
        
        # Always print to console
        print(log_message)
        
        # Write to log file if specified
        if self.log_file:
            # If success_only mode, only write SUCCESS level messages
            if success_only:
                if level == 'SUCCESS':
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(log_message + '\n')
            else:
                # Normal mode - write everything
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_message + '\n')
    
    def validate_csv(self):
        """
        Validate that CSV file exists and has correct format
        
        Returns:
            True if valid, False otherwise
        """
        if not self.csv_file.exists():
            self.log(f"CSV file not found: {self.csv_file}", 'ERROR')
            return False
        
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                # Check for required or valid headers
                valid_headers = ['brand', 'barcode', 'model', 'color', 'style', 
                               'url', 'max_images', 'notes']
                
                if not headers:
                    self.log("CSV file has no headers", 'ERROR')
                    return False
                
                # At least one search parameter header should exist
                search_headers = ['brand', 'barcode', 'model', 'color', 'style', 'url']
                if not any(h in headers for h in search_headers):
                    self.log(f"CSV must have at least one of: {', '.join(search_headers)}", 'ERROR')
                    return False
                
                self.log(f"CSV validated. Headers: {', '.join(headers)}", 'INFO')
                return True
                
        except Exception as e:
            self.log(f"Error validating CSV: {e}", 'ERROR')
            return False
    
    def read_csv_items(self):
        """
        Read items from CSV file
        
        Returns:
            List of dictionaries containing search parameters
        """
        items = []
        
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                    # Clean up empty values
                    item = {}
                    for key, value in row.items():
                        if value and value.strip():
                            item[key.lower()] = value.strip()
                    
                    # Validate item has at least one search parameter
                    search_params = ['brand', 'barcode', 'model', 'color', 'style', 'url']
                    if any(param in item for param in search_params):
                        item['row_number'] = row_num
                        items.append(item)
                    else:
                        self.log(f"Row {row_num}: Skipping - no search parameters", 'WARNING')
            
            self.log(f"Loaded {len(items)} valid items from CSV", 'SUCCESS')
            return items
            
        except Exception as e:
            self.log(f"Error reading CSV: {e}", 'ERROR')
            return []
    
    def process_item(self, item, item_num):
        """
        Process a single item from CSV
        
        Args:
            item: Dictionary with search parameters
            item_num: Item number for display
            
        Returns:
            Number of images downloaded
        """
        row_num = item.get('row_number', '?')
        
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
        display_name = ' '.join(display_parts) if display_parts else f"Row {row_num}"
        
        self.log("="*70, 'INFO')
        self.log(f"Processing Item {item_num}/{self.stats['total_items']}: {display_name}", 'INFO')
        if notes:
            self.log(f"Notes: {notes}", 'INFO')
        
        try:
            # Scrape and download
            result = self.scraper.scrape_and_download(
                brand=brand,
                barcode=barcode,
                model=model,
                color=color,
                style=style,
                specific_url=url,
                max_images=max_images
            )
            
            # Handle both old (list) and new (dict) return formats
            if isinstance(result, dict):
                files = result.get('files', [])
                metadata = result.get('metadata', {})
            else:
                files = result
                metadata = {}
            
            num_images = len(files)
            
            if num_images > 0:
                self.log(f"✓ Success! Downloaded {num_images} images", 'SUCCESS')
                
                # Create detailed success log entry
                success_log_entry = [
                    "="*70,
                    f"SUCCESS: {display_name}",
                    f"Brand: {brand or 'N/A'} | Model: {model or 'N/A'} | Style: {style or 'N/A'} | Color: {color or 'N/A'}",
                    f"Downloaded {num_images} images:",
                ]
                
                # Get image metadata from scraper's download_report
                image_details = []
                if hasattr(self.scraper, 'download_report') and self.scraper.download_report:
                    last_report = self.scraper.download_report[-1]
                    image_details = last_report.get('images', [])
                
                # Log each image with its source URL
                for idx, filepath in enumerate(files):
                    filename = Path(filepath).name
                    
                    # Get image source info
                    if idx < len(image_details):
                        img_info = image_details[idx]
                        img_url = img_info.get('image_url', 'N/A')
                        source_name = img_info.get('source_name', 'Unknown')
                        source_url = img_info.get('source_url', 'N/A')
                        
                        success_log_entry.append(f"  [{idx+1}] {filename}")
                        success_log_entry.append(f"      Image URL: {img_url}")
                        success_log_entry.append(f"      Source: {source_name}")
                        success_log_entry.append(f"      Page URL: {source_url}")
                    else:
                        success_log_entry.append(f"  [{idx+1}] {filename}")
                    
                    # Also log to console briefly
                    self.log(f"  • {filename}", 'INFO')
                
                success_log_entry.append("="*70)
                
                # Write success entry to SUCCESS-ONLY log file
                if self.success_log_file:
                    with open(self.success_log_file, 'a', encoding='utf-8') as f:
                        f.write('\n'.join(success_log_entry) + '\n\n')
                
                # Also write to main log if it exists
                if self.log_file:
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        f.write(f"[{timestamp}] [SUCCESS] Downloaded {num_images} images for {display_name}\n")
                
                self.stats['successful'] += 1
                self.stats['total_images'] += num_images
            else:
                self.log(f"✗ No images found", 'WARNING')
                
                # Add failed item to report
                self.report_data.append({
                    'Brand': brand or '',
                    'Model': model or '',
                    'Style': style or '',
                    'Color': color or '',
                    'Barcode': barcode or '',
                    'Search_Query': ', '.join(metadata.get('search_terms', {}).get('queries', [])) if metadata else '',
                    'Image_Filename': 'NOT FOUND',
                    'Image_URL': 'N/A',
                    'Source': 'N/A',
                    'Notes': notes or ''
                })
                
                self.stats['failed'] += 1
            
            return num_images
            
        except Exception as e:
            self.log(f"✗ Error: {e}", 'ERROR')
            
            # Add error to report
            self.report_data.append({
                'Brand': brand or '',
                'Model': model or '',
                'Style': style or '',
                'Color': color or '',
                'Barcode': barcode or '',
                'Search_Query': '',
                'Image_Filename': 'ERROR',
                'Image_URL': str(e),
                'Source': 'ERROR',
                'Notes': notes or ''
            })
            
            self.stats['failed'] += 1
            return 0
    
    def run(self):
        """
        Main method to process all items from CSV
        """
        self.log("="*70, 'INFO')
        self.log("CSV Batch Scraper Starting", 'INFO')
        self.log(f"CSV File: {self.csv_file}", 'INFO')
        self.log(f"Output Directory: {self.output_dir}", 'INFO')
        self.log("="*70, 'INFO')
        
        # Validate CSV
        if not self.validate_csv():
            return
        
        # Read items
        items = self.read_csv_items()
        
        if not items:
            self.log("No items to process", 'WARNING')
            return
        
        # Initialize stats
        self.stats['total_items'] = len(items)
        self.stats['start_time'] = datetime.now()
        
        # Process each item
        for idx, item in enumerate(items, start=1):
            self.process_item(item, idx)
            
            # Delay between items (except for last item)
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
        
        # Inform about success-only log
        if self.success_log_file and self.stats['successful'] > 0:
            self.log(f"Success-only log (with image URLs): {self.success_log_file}", 'INFO')
        
        # Generate Excel report
        self.generate_excel_report()
    
    def generate_excel_report(self):
        """
        Generate an Excel report with search terms and image links
        """
        try:
            import pandas as pd
            from datetime import datetime
            
            if not self.report_data:
                self.log("No data to generate report", 'WARNING')
                return
            
            # Create DataFrame
            df = pd.DataFrame(self.report_data)
            
            # Generate report filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = self.output_dir / f'scraping_report_{timestamp}.xlsx'
            
            # Write to Excel with formatting
            with pd.ExcelWriter(report_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Results', index=False)
                
                # Get the workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['Results']
                
                # Auto-adjust column widths
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    
                    adjusted_width = min(max_length + 2, 50)  # Cap at 50
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Make header row bold
                from openpyxl.styles import Font, PatternFill
                header_font = Font(bold=True)
                header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                
                for cell in worksheet[1]:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = header_fill
            
            self.log(f"Excel report generated: {report_file}", 'SUCCESS')
            print(f"\n📊 Excel Report: {report_file}")
            
        except ImportError:
            self.log("Warning: pandas and openpyxl required for Excel reports", 'WARNING')
            self.log("Install with: pip install pandas openpyxl", 'INFO')
        except Exception as e:
            self.log(f"Error generating Excel report: {e}", 'ERROR')


def create_sample_csv(filename="items.csv"):
    """
    Create a sample CSV file with example data
    
    Args:
        filename: Name of CSV file to create
    """
    sample_data = [
        {
            'brand': 'stuart weitzman',
            'model': 'SD166',
            'style': 'GEMCUT 85 SANDAL',
            'color': '',
            'barcode': '',
            'url': '',
            'max_images': '5',
            'notes': 'Example from original request'
        },
        {
            'brand': 'Nike',
            'model': 'Air Max 270',
            'style': 'Running Shoe',
            'color': 'Black',
            'barcode': '',
            'url': '',
            'max_images': '3',
            'notes': 'Popular running shoe'
        },
        {
            'brand': 'Adidas',
            'model': '',
            'style': 'Ultraboost',
            'color': 'White',
            'barcode': '',
            'url': '',
            'max_images': '4',
            'notes': ''
        },
        {
            'brand': '',
            'model': '',
            'style': '',
            'color': '',
            'barcode': '',
            'url': 'https://tjmaxx.tjx.com/store/jump/product/Made-In-Spain-Suede-Gemcut-85-Heeled-Sandals/1001136525',
            'max_images': '5',
            'notes': 'Using direct URL instead of search'
        }
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['brand', 'model', 'style', 'color', 'barcode', 'url', 'max_images', 'notes']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(sample_data)
    
    print(f"Sample CSV created: {filename}")
    print(f"Edit this file and add your items, then run:")
    print(f"  python csv_scraper.py {filename}")


def main():
    parser = argparse.ArgumentParser(
        description='CSV-based Clothing Image Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process items from CSV file
  python csv_scraper.py items.csv
  
  # Custom output directory
  python csv_scraper.py items.csv --output ./my_images
  
  # Create sample CSV file
  python csv_scraper.py --create-sample items.csv
  
  # Process with custom delay and logging
  python csv_scraper.py items.csv --delay 5 --log scraper.log

CSV Format:
  Your CSV should have these columns (at least one search parameter required):
  - brand: Brand name
  - model: Model number
  - style: Style name
  - color: Color
  - barcode: Product barcode
  - url: Direct product URL (alternative to search)
  - max_images: Number of images to download (default: 5)
  - notes: Optional notes (not used for search)
        """
    )
    
    parser.add_argument('csv_file', nargs='?', help='Path to CSV file with search parameters')
    parser.add_argument('--output', type=str, default='./downloaded_images',
                       help='Output directory for images (default: ./downloaded_images)')
    parser.add_argument('--delay', type=int, default=2,
                       help='Delay between items in seconds (default: 2)')
    parser.add_argument('--log', type=str, help='Log file path (optional)')
    parser.add_argument('--create-sample', metavar='FILENAME', 
                       help='Create a sample CSV file and exit')
    
    args = parser.parse_args()
    
    # Create sample CSV if requested
    if args.create_sample:
        create_sample_csv(args.create_sample)
        return
    
    # Validate CSV file argument
    if not args.csv_file:
        parser.print_help()
        print("\nError: csv_file is required (or use --create-sample)")
        return
    
    # Create and run scraper
    scraper = CSVBatchScraper(
        csv_file=args.csv_file,
        output_dir=args.output,
        delay_between_items=args.delay,
        log_file=args.log
    )
    
    scraper.run()


if __name__ == "__main__":
    main()
