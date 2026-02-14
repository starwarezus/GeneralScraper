"""
Image Hash Index
Perceptual hashing-based duplicate detection for downloaded images.
Uses MD5 for exact matches and pHash/dHash for near-duplicate detection.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image
    import imagehash
    HASH_LIBS_AVAILABLE = True
except ImportError:
    HASH_LIBS_AVAILABLE = False
    print("Warning: Pillow and/or imagehash not installed. Perceptual hashing disabled.")
    print("Install with: pip install Pillow imagehash")


class ImageHashIndex:
    def __init__(self, index_file="image_hashes.json", similarity_threshold=10):
        """
        Initialize the image hash index.

        Args:
            index_file: Path to the persistent JSON index file
            similarity_threshold: Hamming distance threshold for perceptual hash comparison.
                                  Lower = stricter matching.
        """
        self.index_file = Path(index_file)
        self.similarity_threshold = similarity_threshold
        self.index = {}  # key: md5 -> entry dict
        self.phash_map = {}  # key: phash_str -> list of md5s
        self._load()

    def _load(self):
        """Load the hash index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.index = data.get('index', {})
                self.phash_map = data.get('phash_map', {})
                print(f"  Loaded hash index with {len(self.index)} entries")
            except (json.JSONDecodeError, KeyError):
                self.index = {}
                self.phash_map = {}

    def _save(self):
        """Save the hash index to disk."""
        data = {
            'index': self.index,
            'phash_map': self.phash_map,
        }
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _compute_md5(self, filepath):
        """Compute MD5 hash of a file."""
        md5 = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()

    def _compute_perceptual_hashes(self, filepath):
        """
        Compute perceptual hashes (pHash and dHash) for an image.

        Returns:
            Tuple of (phash_str, dhash_str) or (None, None) if unable to compute
        """
        if not HASH_LIBS_AVAILABLE:
            return None, None

        try:
            img = Image.open(filepath)
            phash = str(imagehash.phash(img))
            dhash = str(imagehash.dhash(img))
            return phash, dhash
        except Exception as e:
            print(f"  Warning: Could not compute perceptual hash for {filepath}: {e}")
            return None, None

    def is_duplicate(self, filepath):
        """
        Check if an image is a duplicate of an already-indexed image.

        First checks MD5 (exact match), then pHash (near-match).

        Args:
            filepath: Path to the image file to check

        Returns:
            Tuple of (is_dup: bool, original_path: str or None, match_type: str or None)
            match_type is 'exact' for MD5 match, 'perceptual' for pHash near-match
        """
        filepath = Path(filepath)
        if not filepath.exists():
            return False, None, None

        # Step 1: Check MD5 (exact duplicate)
        md5 = self._compute_md5(filepath)
        if md5 in self.index:
            original = self.index[md5].get('filepath', 'unknown')
            return True, original, 'exact'

        # Step 2: Check perceptual hash (near duplicate)
        if HASH_LIBS_AVAILABLE:
            phash_str, dhash_str = self._compute_perceptual_hashes(filepath)
            if phash_str:
                try:
                    new_phash = imagehash.hex_to_hash(phash_str)
                    for existing_phash_str, md5_list in self.phash_map.items():
                        existing_phash = imagehash.hex_to_hash(existing_phash_str)
                        distance = new_phash - existing_phash
                        if distance <= self.similarity_threshold:
                            # Found a near-match
                            if md5_list:
                                original_md5 = md5_list[0]
                                original = self.index.get(original_md5, {}).get('filepath', 'unknown')
                                return True, original, 'perceptual'
                except Exception:
                    pass

        return False, None, None

    def add_image(self, filepath, item_name=""):
        """
        Compute hashes and add an image to the index.

        Args:
            filepath: Path to the image file
            item_name: Human-readable name for the item

        Returns:
            The MD5 hash of the added image
        """
        filepath = Path(filepath)
        md5 = self._compute_md5(filepath)
        phash_str, dhash_str = self._compute_perceptual_hashes(filepath)

        entry = {
            'filepath': str(filepath),
            'md5': md5,
            'phash': phash_str,
            'dhash': dhash_str,
            'item_name': item_name,
            'timestamp': datetime.now().isoformat(),
        }

        self.index[md5] = entry

        # Add to phash map for fast perceptual lookups
        if phash_str:
            if phash_str not in self.phash_map:
                self.phash_map[phash_str] = []
            if md5 not in self.phash_map[phash_str]:
                self.phash_map[phash_str].append(md5)

        self._save()
        return md5

    def remove_image(self, filepath):
        """
        Remove an image from the index by filepath.

        Args:
            filepath: Path to the image file to remove
        """
        filepath_str = str(Path(filepath))
        md5_to_remove = None
        for md5, entry in self.index.items():
            if entry.get('filepath') == filepath_str:
                md5_to_remove = md5
                break

        if md5_to_remove:
            phash_str = self.index[md5_to_remove].get('phash')
            del self.index[md5_to_remove]
            if phash_str and phash_str in self.phash_map:
                self.phash_map[phash_str] = [m for m in self.phash_map[phash_str] if m != md5_to_remove]
                if not self.phash_map[phash_str]:
                    del self.phash_map[phash_str]
            self._save()

    def get_duplicate_report(self):
        """
        Generate a summary report of all indexed images and potential duplicate groups.

        Returns:
            Dict with 'total_images', 'unique_phashes', 'duplicate_groups' (list of groups)
        """
        duplicate_groups = []
        for phash_str, md5_list in self.phash_map.items():
            if len(md5_list) > 1:
                group = []
                for md5 in md5_list:
                    entry = self.index.get(md5, {})
                    group.append({
                        'filepath': entry.get('filepath', 'unknown'),
                        'item_name': entry.get('item_name', ''),
                        'md5': md5,
                    })
                duplicate_groups.append({
                    'phash': phash_str,
                    'count': len(md5_list),
                    'images': group,
                })

        return {
            'total_images': len(self.index),
            'unique_phashes': len(self.phash_map),
            'duplicate_groups': duplicate_groups,
        }
