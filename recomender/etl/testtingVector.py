#!/usr/bin/env python3
"""
Script to print and inspect embedding vectors
"""

import numpy as np
import pandas as pd
import pickle
from pathlib import Path


def print_clip_embeddings(limit=5):
    """Print CLIP embeddings"""
    print("\n" + "="*70)
    print("CLIP EMBEDDINGS (512-dim)")
    print("="*70)
    
    # Load embeddings
    embeddings = np.load("./data/processed/clip_item_embeddings.npy")
    variant_ids = np.load("./data/processed/variant_ids.npy")
    
    print(f"Total embeddings: {len(embeddings)}")
    print(f"Embedding dimension: {embeddings.shape[1]}")
    print(f"Data type: {embeddings.dtype}")
    print(f"Memory size: {embeddings.nbytes / 1024 / 1024:.2f} MB")
    
    # Print sample embeddings
    print(f"\n Sample {limit} embeddings:\n")
    for i in range(min(limit, len(embeddings))):
        variant_id = variant_ids[i]
        vector = embeddings[i]
        
        print(f"Variant ID: {variant_id}")
        print(f"Vector shape: {vector.shape}")
        print(f"Vector norm: {np.linalg.norm(vector):.6f}")
        print(f"Min value: {vector.min():.6f}")
        print(f"Max value: {vector.max():.6f}")
        print(f"Mean value: {vector.mean():.6f}")
        print(f"First 10 values: {vector[:10]}")
        print(f"Last 10 values: {vector[-10:]}")
        print("-" * 70)


def print_bert_embeddings(limit=5):
    """Print BERT embeddings"""
    print("\n" + "="*70)
    print(" BERT METADATA EMBEDDINGS (768-dim)")
    print("="*70)
    
    # Load embeddings
    embeddings = np.load("./data/processed/bert_metadata_embeddings.npy")
    variant_ids = np.load("./data/processed/variant_ids.npy")
    
    print(f"Total embeddings: {len(embeddings)}")
    print(f"Embedding dimension: {embeddings.shape[1]}")
    print(f"Data type: {embeddings.dtype}")
    print(f"Memory size: {embeddings.nbytes / 1024 / 1024:.2f} MB")
    
    # Print sample embeddings
    print(f"\n Sample {limit} embeddings:\n")
    for i in range(min(limit, len(embeddings))):
        variant_id = variant_ids[i]
        vector = embeddings[i]
        
        print(f"Variant ID: {variant_id}")
        print(f"Vector shape: {vector.shape}")
        print(f"Vector norm: {np.linalg.norm(vector):.6f}")
        print(f"Min value: {vector.min():.6f}")
        print(f"Max value: {vector.max():.6f}")
        print(f"Mean value: {vector.mean():.6f}")
        print(f"First 10 values: {vector[:10]}")
        print(f"Last 10 values: {vector[-10:]}")
        print("-" * 70)


def print_hybrid_embeddings(limit=5):
    """Print Hybrid embeddings"""
    print("\n" + "="*70)
    print(" HYBRID EMBEDDINGS (CLIP + BERT)")
    print("="*70)
    
    # Load embeddings
    embeddings = np.load("./data/processed/hybrid_embeddings.npy")
    variant_ids = np.load("./data/processed/variant_ids.npy")
    
    print(f"Total embeddings: {len(embeddings)}")
    print(f"Embedding dimension: {embeddings.shape[1]}")
    print(f"Data type: {embeddings.dtype}")
    print(f"Memory size: {embeddings.nbytes / 1024 / 1024:.2f} MB")
    
    # Print sample embeddings
    print(f"\nSample {limit} embeddings:\n")
    for i in range(min(limit, len(embeddings))):
        variant_id = variant_ids[i]
        vector = embeddings[i]
        
        print(f"Variant ID: {variant_id}")
        print(f"Vector shape: {vector.shape}")
        print(f"Vector norm: {np.linalg.norm(vector):.6f}")
        print(f"Min value: {vector.min():.6f}")
        print(f"Max value: {vector.max():.6f}")
        print(f"Mean value: {vector.mean():.6f}")
        print(f"First 10 values: {vector[:10]}")
        print(f"Last 10 values: {vector[-10:]}")
        print("-" * 70)


def print_embedding_with_metadata(variant_id):
    """Print embedding with product metadata"""
    print("\n" + "="*70)
    print(f" DETAILED VIEW: Variant {variant_id}")
    print("="*70)
    
    # Load item features
    item_features = pd.read_csv("./data/processed/item_features.csv")
    
    # Find product
    product = item_features[item_features['variant_id'] == str(variant_id)]
    
    if len(product) == 0:
        print(f" Variant {variant_id} not found!")
        return
    
    product = product.iloc[0]
    
    # Print metadata
    print("\nPRODUCT METADATA:")
    print(f"  Product Name: {product.get('product_name', 'N/A')}")
    print(f"  Category: {product.get('category_name', 'N/A')}")
    print(f"  Color: {product.get('color_name', 'N/A')}")
    print(f"  Size: {product.get('size', 'N/A')}")
    print(f"  Price: ${product.get('price', 0):.2f}")
    print(f"  Price Range: {product.get('price_range', 'N/A')}")
    print(f"  Rating: {product.get('avg_rating', 0):.2f}/5.0")
    print(f"  Popularity Score: {product.get('popularity_score', 0):.2f}")
    
    # Load embeddings
    variant_ids = np.load("./data/processed/variant_ids.npy")
    
    # Find index
    try:
        idx = np.where(variant_ids == str(variant_id))[0][0]
    except IndexError:
        print(f"Embedding not found for variant {variant_id}")
        return
    
    # Print CLIP embedding
    if Path("./data/processed/clip_item_embeddings.npy").exists():
        clip_emb = np.load("./data/processed/clip_item_embeddings.npy")
        print("\n CLIP EMBEDDING (512-dim):")
        print(f"  Vector: {clip_emb[idx][:20]}... (showing first 20)")
        print(f"  Norm: {np.linalg.norm(clip_emb[idx]):.6f}")
    
    # Print BERT embedding
    if Path("./data/processed/bert_metadata_embeddings.npy").exists():
        bert_emb = np.load("./data/processed/bert_metadata_embeddings.npy")
        print("\n BERT EMBEDDING (768-dim):")
        print(f"  Vector: {bert_emb[idx][:20]}... (showing first 20)")
        print(f"  Norm: {np.linalg.norm(bert_emb[idx]):.6f}")
    
    # Print Hybrid embedding
    if Path("./data/processed/hybrid_embeddings.npy").exists():
        hybrid_emb = np.load("./data/processed/hybrid_embeddings.npy")
        print("\n HYBRID EMBEDDING:")
        print(f"  Dimension: {hybrid_emb.shape[1]}")
        print(f"  Vector: {hybrid_emb[idx][:20]}... (showing first 20)")
        print(f"  Norm: {np.linalg.norm(hybrid_emb[idx]):.6f}")


def compare_embeddings(variant_id1, variant_id2):
    """Compare embeddings between two variants"""
    print("\n" + "="*70)
    print(f" COMPARING: Variant {variant_id1} vs {variant_id2}")
    print("="*70)
    
    # Load data
    variant_ids = np.load("./data/processed/variant_ids.npy")
    
    try:
        idx1 = np.where(variant_ids == str(variant_id1))[0][0]
        idx2 = np.where(variant_ids == str(variant_id2))[0][0]
    except IndexError:
        print("❌ One or both variants not found!")
        return
    
    # Load item features
    item_features = pd.read_csv("./data/processed/item_features.csv")
    p1 = item_features[item_features['variant_id'] == str(variant_id1)].iloc[0]
    p2 = item_features[item_features['variant_id'] == str(variant_id2)].iloc[0]
    
    print(f"\n Product 1: {p1.get('product_name', 'N/A')}")
    print(f" Product 2: {p2.get('product_name', 'N/A')}")
    
    # Compare CLIP embeddings
    if Path("./data/processed/clip_item_embeddings.npy").exists():
        clip_emb = np.load("./data/processed/clip_item_embeddings.npy")
        v1 = clip_emb[idx1]
        v2 = clip_emb[idx2]
        
        # Cosine similarity
        cosine_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        
        # Euclidean distance
        euclidean_dist = np.linalg.norm(v1 - v2)
        
        print(f"\n🎨 CLIP Similarity:")
        print(f"  Cosine Similarity: {cosine_sim:.6f}")
        print(f"  Euclidean Distance: {euclidean_dist:.6f}")
    
    # Compare Hybrid embeddings
    if Path("./data/processed/hybrid_embeddings.npy").exists():
        hybrid_emb = np.load("./data/processed/hybrid_embeddings.npy")
        v1 = hybrid_emb[idx1]
        v2 = hybrid_emb[idx2]
        
        cosine_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        euclidean_dist = np.linalg.norm(v1 - v2)
        
        print(f"\n🔗 Hybrid Similarity:")
        print(f"  Cosine Similarity: {cosine_sim:.6f}")
        print(f"  Euclidean Distance: {euclidean_dist:.6f}")


def print_statistics():
    """Print overall statistics"""
    print("\n" + "="*70)
    print(" EMBEDDING STATISTICS")
    print("="*70)
    
    files = {
        "CLIP": "./data/processed/clip_item_embeddings.npy",
        "BERT": "./data/processed/bert_metadata_embeddings.npy",
        "Hybrid": "./data/processed/hybrid_embeddings.npy"
    }
    
    for name, filepath in files.items():
        if Path(filepath).exists():
            emb = np.load(filepath)
            print(f"\n{name} Embeddings:")
            print(f"  Shape: {emb.shape}")
            print(f"  Mean norm: {np.linalg.norm(emb, axis=1).mean():.6f}")
            print(f"  Std norm: {np.linalg.norm(emb, axis=1).std():.6f}")
            print(f"  Min value: {emb.min():.6f}")
            print(f"  Max value: {emb.max():.6f}")
            print(f"  Mean value: {emb.mean():.6f}")
            print(f"  Std value: {emb.std():.6f}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Print and inspect embeddings")
    parser.add_argument("--clip", action="store_true", help="Print CLIP embeddings")
    parser.add_argument("--bert", action="store_true", help="Print BERT embeddings")
    parser.add_argument("--hybrid", action="store_true", help="Print Hybrid embeddings")
    parser.add_argument("--all", action="store_true", help="Print all embeddings")
    parser.add_argument("--limit", type=int, default=5, help="Number of samples to print")
    parser.add_argument("--variant", type=str, help="Print specific variant embedding")
    parser.add_argument("--compare", nargs=2, help="Compare two variants")
    parser.add_argument("--stats", action="store_true", help="Print statistics")
    
    args = parser.parse_args()
    
    if args.stats:
        print_statistics()
    
    if args.variant:
        print_embedding_with_metadata(args.variant)
    
    if args.compare:
        compare_embeddings(args.compare[0], args.compare[1])
    
    if args.clip or args.all:
        print_clip_embeddings(args.limit)
    
    if args.bert or args.all:
        print_bert_embeddings(args.limit)
    
    if args.hybrid or args.all:
        print_hybrid_embeddings(args.limit)
    
    if not any([args.clip, args.bert, args.hybrid, args.all, args.variant, args.compare, args.stats]):
        parser.print_help()


if __name__ == "__main__":
    main()