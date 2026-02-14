#!/usr/bin/env python3
"""
GUI Interface for Clothing Image Scraper
Simple tkinter-based interface for non-technical users
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import sys
import os
from pathlib import Path

# Add current directory to path to import ClothingImageScraper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from clothing_image_scraper import ClothingImageScraper
except ImportError:
    # If running as GUI, show error dialog
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Error", 
        "clothing_image_scraper.py not found!\n\n"
        "Please make sure clothing_image_scraper.py is in the same folder as gui_scraper.py")
    sys.exit(1)


class ScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Clothing Image Scraper")
        self.root.geometry("700x650")
        
        # Default download path
        self.download_path = Path.home() / "Downloads" / "clothing_images"
        
        self.create_widgets()
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Clothing Image Scraper", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Search Parameters Frame
        params_frame = ttk.LabelFrame(main_frame, text="Search Parameters", padding="10")
        params_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Brand
        ttk.Label(params_frame, text="Brand:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.brand_entry = ttk.Entry(params_frame, width=40)
        self.brand_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Model
        ttk.Label(params_frame, text="Model:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.model_entry = ttk.Entry(params_frame, width=40)
        self.model_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Style
        ttk.Label(params_frame, text="Style:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.style_entry = ttk.Entry(params_frame, width=40)
        self.style_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Color
        ttk.Label(params_frame, text="Color:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.color_entry = ttk.Entry(params_frame, width=40)
        self.color_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Barcode
        ttk.Label(params_frame, text="Barcode:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.barcode_entry = ttk.Entry(params_frame, width=40)
        self.barcode_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # URL (alternative)
        ttk.Label(params_frame, text="Or URL:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(params_frame, width=40)
        self.url_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Settings Frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Max Images
        ttk.Label(settings_frame, text="Max Images:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.max_images_spinbox = ttk.Spinbox(settings_frame, from_=1, to=20, width=10)
        self.max_images_spinbox.set(5)
        self.max_images_spinbox.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Download Path
        ttk.Label(settings_frame, text="Download Path:").grid(row=1, column=0, sticky=tk.W, pady=5)
        path_frame = ttk.Frame(settings_frame)
        path_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        self.path_label = ttk.Label(path_frame, text=str(self.download_path), 
                                    relief=tk.SUNKEN, width=35)
        self.path_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        browse_btn = ttk.Button(path_frame, text="Browse", command=self.browse_path)
        browse_btn.grid(row=0, column=1, padx=5)
        
        # Buttons Frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        self.scrape_btn = ttk.Button(button_frame, text="Start Scraping", 
                                     command=self.start_scraping)
        self.scrape_btn.grid(row=0, column=0, padx=5)
        
        clear_btn = ttk.Button(button_frame, text="Clear All", 
                              command=self.clear_fields)
        clear_btn.grid(row=0, column=1, padx=5)
        
        # Example button
        example_btn = ttk.Button(button_frame, text="Load Example", 
                                command=self.load_example)
        example_btn.grid(row=0, column=2, padx=5)
        
        # Progress
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Log Frame
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=70)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(5, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
    def browse_path(self):
        """Open directory browser"""
        path = filedialog.askdirectory(initialdir=self.download_path)
        if path:
            self.download_path = Path(path)
            self.path_label.config(text=str(self.download_path))
    
    def log(self, message):
        """Add message to log"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_fields(self):
        """Clear all input fields"""
        self.brand_entry.delete(0, tk.END)
        self.model_entry.delete(0, tk.END)
        self.style_entry.delete(0, tk.END)
        self.color_entry.delete(0, tk.END)
        self.barcode_entry.delete(0, tk.END)
        self.url_entry.delete(0, tk.END)
        self.log_text.delete(1.0, tk.END)
    
    def load_example(self):
        """Load example data"""
        self.clear_fields()
        self.brand_entry.insert(0, "stuart weitzman")
        self.model_entry.insert(0, "SD166")
        self.style_entry.insert(0, "GEMCUT 85 SANDAL")
        self.log("Example data loaded - Stuart Weitzman SD166 GEMCUT 85 SANDAL")
    
    def scrape_thread(self):
        """Run scraping in separate thread"""
        try:
            # Get values
            brand = self.brand_entry.get().strip() or None
            model = self.model_entry.get().strip() or None
            style = self.style_entry.get().strip() or None
            color = self.color_entry.get().strip() or None
            barcode = self.barcode_entry.get().strip() or None
            url = self.url_entry.get().strip() or None
            max_images = int(self.max_images_spinbox.get())
            
            # Validate
            if not any([brand, model, style, color, barcode, url]):
                messagebox.showerror("Error", "Please enter at least one search parameter or URL")
                return
            
            self.log("="*50)
            self.log("Starting scraper...")
            self.log(f"Download path: {self.download_path}")
            
            # Create scraper
            scraper = ClothingImageScraper(download_path=str(self.download_path))
            
            # Scrape
            files = scraper.scrape_and_download(
                brand=brand,
                model=model,
                style=style,
                color=color,
                barcode=barcode,
                specific_url=url,
                max_images=max_images
            )
            
            self.log(f"\nCompleted! Downloaded {len(files)} images:")
            for f in files:
                self.log(f"  ✓ {Path(f).name}")
            
            messagebox.showinfo("Success", f"Downloaded {len(files)} images!")
            
        except Exception as e:
            self.log(f"\nError: {str(e)}")
            messagebox.showerror("Error", f"Scraping failed: {str(e)}")
        
        finally:
            self.progress.stop()
            self.scrape_btn.config(state=tk.NORMAL)
    
    def start_scraping(self):
        """Start scraping process"""
        self.scrape_btn.config(state=tk.DISABLED)
        self.progress.start()
        
        # Run in thread to prevent GUI freeze
        thread = threading.Thread(target=self.scrape_thread, daemon=True)
        thread.start()


def main():
    root = tk.Tk()
    app = ScraperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
