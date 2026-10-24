#!/usr/bin/env python3
"""
Pre-calculate CLIP embeddings for workshop datasets.

This script processes all images in a directory and saves their embeddings
to a file that students can use during the workshop without needing a GPU.

INSTRUCTOR USE ONLY - The output embeddings file is shared with students.

Example Usage (Uppsala University collection):
    python precalculate_embeddings.py \\
        --images_dir ../data/images/Uppsala_University \\
        --output ../data/embeddings/uppsala_university_clip_embeddings.npz \\
        --model ViT-B/32

Example Usage (Custom collection):
    python precalculate_embeddings.py \\
        --images_dir ../data/images/My_Collection \\
        --output ../data/embeddings/my_collection_clip_embeddings.npz \\
        --model ViT-B/32 \\
        --batch_size 64

Requirements:
    pip install torch torchvision pillow tqdm numpy
    pip install git+https://github.com/openai/CLIP.git
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from tqdm import tqdm

# Try to import CLIP
try:
    import clip
except ImportError:
    print("Please install CLIP: pip install git+https://github.com/openai/CLIP.git")
    sys.exit(1)


def get_image_files(directory: Path, extensions=('.jpg', '.jpeg', '.png', '.webp')):
    """Recursively find all image files in a directory."""
    image_files = []
    for ext in extensions:
        image_files.extend(directory.rglob(f'*{ext}'))
        image_files.extend(directory.rglob(f'*{ext.upper()}'))
    return sorted(set(image_files))


def calculate_embeddings(
    images_dir: Path,
    output_path: Path,
    model_name: str = 'ViT-B/32',
    batch_size: int = 32,
    device: str = None
):
    """
    Calculate CLIP embeddings for all images in a directory.

    Args:
        images_dir: Directory containing images
        output_path: Path to save the embeddings (.npz file)
        model_name: CLIP model to use (ViT-B/32 is fastest, ViT-L/14 is most accurate)
        batch_size: Number of images to process at once
        device: 'cuda', 'cpu', or None for auto-detect
    """
    # Set device
    if device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")

    # Load CLIP model
    print(f"Loading CLIP model: {model_name}")
    model, preprocess = clip.load(model_name, device=device)
    model.eval()

    # Find all images
    print(f"Scanning for images in: {images_dir}")
    image_files = get_image_files(images_dir)
    print(f"Found {len(image_files)} images")

    if len(image_files) == 0:
        print("No images found! Check the directory path.")
        return

    # Process images in batches
    all_embeddings = []
    all_filenames = []
    failed_images = []

    print(f"Processing images in batches of {batch_size}...")

    for i in tqdm(range(0, len(image_files), batch_size), desc="Processing"):
        batch_files = image_files[i:i + batch_size]
        batch_images = []
        batch_names = []

        for img_path in batch_files:
            try:
                image = Image.open(img_path).convert('RGB')
                image_tensor = preprocess(image)
                batch_images.append(image_tensor)
                batch_names.append(str(img_path.relative_to(images_dir)))
            except Exception as e:
                failed_images.append((str(img_path), str(e)))
                continue

        if batch_images:
            # Stack and encode
            batch_tensor = torch.stack(batch_images).to(device)

            with torch.no_grad():
                embeddings = model.encode_image(batch_tensor)
                # Normalize embeddings
                embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)
                embeddings = embeddings.cpu().numpy()

            all_embeddings.append(embeddings)
            all_filenames.extend(batch_names)

    # Concatenate all embeddings
    embeddings_array = np.vstack(all_embeddings)

    print(f"\nSuccessfully processed {len(all_filenames)} images")
    print(f"Embeddings shape: {embeddings_array.shape}")

    if failed_images:
        print(f"Failed to process {len(failed_images)} images:")
        for path, error in failed_images[:10]:
            print(f"  - {path}: {error}")
        if len(failed_images) > 10:
            print(f"  ... and {len(failed_images) - 10} more")

    # Save embeddings
    output_path.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        output_path,
        embeddings=embeddings_array,
        filenames=np.array(all_filenames, dtype=object),
        model_name=model_name,
        embedding_dim=embeddings_array.shape[1]
    )

    print(f"\nSaved embeddings to: {output_path}")
    print(f"File size: {output_path.stat().st_size / (1024*1024):.1f} MB")

    # Also save a JSON index for easy lookup
    index_path = output_path.with_suffix('.json')
    with open(index_path, 'w') as f:
        json.dump({
            'model_name': model_name,
            'embedding_dim': int(embeddings_array.shape[1]),
            'num_images': len(all_filenames),
            'filenames': all_filenames
        }, f, indent=2)
    print(f"Saved index to: {index_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Pre-calculate CLIP embeddings for images'
    )
    parser.add_argument(
        '--images_dir', '-i',
        type=Path,
        required=True,
        help='Directory containing images'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path('embeddings.npz'),
        help='Output file path (default: embeddings.npz)'
    )
    parser.add_argument(
        '--model', '-m',
        type=str,
        default='ViT-B/32',
        choices=['RN50', 'RN101', 'RN50x4', 'RN50x16', 'ViT-B/32', 'ViT-B/16', 'ViT-L/14'],
        help='CLIP model to use (default: ViT-B/32)'
    )
    parser.add_argument(
        '--batch_size', '-b',
        type=int,
        default=32,
        help='Batch size for processing (default: 32)'
    )
    parser.add_argument(
        '--device', '-d',
        type=str,
        choices=['cuda', 'cpu'],
        default=None,
        help='Device to use (default: auto-detect)'
    )

    args = parser.parse_args()

    if not args.images_dir.exists():
        print(f"Error: Images directory does not exist: {args.images_dir}")
        sys.exit(1)

    calculate_embeddings(
        images_dir=args.images_dir,
        output_path=args.output,
        model_name=args.model,
        batch_size=args.batch_size,
        device=args.device
    )


if __name__ == '__main__':
    main()
