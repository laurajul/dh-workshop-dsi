#!/usr/bin/env python3
"""
Batch download images from the Finnish National Gallery dataset.

This script downloads images from objects.json for pre-calculating CLIP embeddings.

Usage:
    python download_images_batch.py --metadata ../data/objects.json --output ../images/all_images --resolution 500 --max 5000

Requirements:
    pip install requests tqdm
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """Remove problematic characters from filenames."""
    if not name:
        return "unknown"
    safe = "".join(c for c in name if c.isalnum() or c in ' ._-')
    return safe.strip()[:max_length]


def download_image(url: str, output_path: Path, timeout: int = 30) -> bool:
    """Download a single image."""
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception:
        return False


def get_image_info(obj: dict, resolution: str) -> tuple:
    """Extract image URL and create filename from an object."""
    multimedia = obj.get('multimedia', [])
    if not multimedia:
        return None, None

    # Get first image
    media = multimedia[0]
    image_url = media.get('jpg', {}).get(resolution)
    if not image_url:
        return None, None

    # Create filename
    object_id = obj.get('objectId', 'unknown')

    people = obj.get('people', [])
    if people:
        artist = f"{people[0].get('firstName', '')}_{people[0].get('familyName', '')}".strip('_')
        artist = sanitize_filename(artist, 30)
    else:
        artist = "Unknown"

    filename = f"{artist}_{object_id}.jpg"

    return image_url, filename


def download_dataset(
    metadata_path: Path,
    output_dir: Path,
    resolution: str = '500',
    max_images: int = None,
    workers: int = 4,
    delay: float = 0.1
):
    """Download images from the Finnish National Gallery dataset."""

    # Load metadata
    print(f"Loading metadata from {metadata_path}...")
    with open(metadata_path, 'r', encoding='utf-8') as f:
        objects = json.load(f)
    print(f"Loaded {len(objects)} objects")

    # Filter to objects with images
    objects_with_images = [obj for obj in objects if obj.get('multimedia')]
    print(f"Objects with images: {len(objects_with_images)}")

    # Apply max limit
    if max_images:
        objects_with_images = objects_with_images[:max_images]
        print(f"Limited to {len(objects_with_images)} images")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare download tasks
    tasks = []
    for obj in objects_with_images:
        url, filename = get_image_info(obj, resolution)
        if url and filename:
            output_path = output_dir / filename
            if not output_path.exists():
                tasks.append((url, output_path))

    print(f"Images to download: {len(tasks)} (skipping {len(objects_with_images) - len(tasks)} existing)")

    if not tasks:
        print("No new images to download!")
        return

    # Download with progress bar
    downloaded = 0
    failed = 0

    with tqdm(total=len(tasks), desc="Downloading") as pbar:
        for url, output_path in tasks:
            if download_image(url, output_path):
                downloaded += 1
            else:
                failed += 1
            pbar.update(1)
            time.sleep(delay)  # Rate limiting

    print(f"\nDownload complete!")
    print(f"  Downloaded: {downloaded}")
    print(f"  Failed: {failed}")
    print(f"  Output directory: {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='Batch download Finnish National Gallery images'
    )
    parser.add_argument(
        '--metadata', '-m',
        type=Path,
        required=True,
        help='Path to objects.json metadata file'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path('images'),
        help='Output directory for images (default: images)'
    )
    parser.add_argument(
        '--resolution', '-r',
        type=str,
        choices=['25', '250', '500', '1000', '2000', '4000'],
        default='500',
        help='Image resolution (default: 500)'
    )
    parser.add_argument(
        '--max', '-n',
        type=int,
        default=None,
        help='Maximum number of images to download (default: all)'
    )
    parser.add_argument(
        '--delay', '-d',
        type=float,
        default=0.1,
        help='Delay between downloads in seconds (default: 0.1)'
    )

    args = parser.parse_args()

    if not args.metadata.exists():
        print(f"Error: Metadata file not found: {args.metadata}")
        sys.exit(1)

    download_dataset(
        metadata_path=args.metadata,
        output_dir=args.output,
        resolution=args.resolution,
        max_images=args.max,
        delay=args.delay
    )


if __name__ == '__main__':
    main()
