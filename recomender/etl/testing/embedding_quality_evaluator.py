"""
Embedding Quality Evaluator
============================
Test CLIP/BERT embeddings WITHOUT interaction data
Using synthetic test cases based on business logic

Metrics:
1. Category Coherence (products in same category should be similar)
2. Price-Quality Correlation (similar price → similar products?)
3. Visual-Text Alignment (image vs text embedding consistency)
4. Manual Test Cases (curated similar/dissimilar pairs)
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
import logging
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EmbeddingQualityEvaluator:
    """
    Evaluate embedding quality without user interaction data
    """
    
    def __init__(self, 
                 embeddings: np.ndarray,
                 metadata_df: pd.DataFrame,
                 embedding_type: str = "CLIP"):
        """
        Args:
            embeddings: (N, 512) embedding matrix
            metadata_df: DataFrame with variant_id and metadata
            embedding_type: "CLIP", "BERT", or "Hybrid"
        """
        self.embeddings = embeddings
        self.metadata_df = metadata_df.copy()
        self.embedding_type = embedding_type
        
        # Create variant_id to index mapping
        self.variant_ids = metadata_df['variant_id'].values
        self.id_to_idx = {vid: idx for idx, vid in enumerate(self.variant_ids)}
        
        logger.info(f"Initialized evaluator for {embedding_type}")
        logger.info(f"  Embeddings: {embeddings.shape}")
        logger.info(f"  Products: {len(metadata_df)}")
    
    def get_embedding(self, variant_id: str) -> np.ndarray:
        """Get embedding vector for a variant_id"""
        idx = self.id_to_idx.get(variant_id)
        if idx is None:
            return None
        return self.embeddings[idx]
    
    # ========================================================================
    # TEST 1: CATEGORY COHERENCE
    # ========================================================================
    
    def test_category_coherence(self, sample_size: int = 50) -> Dict:
        """
        Test: Products in same category should have higher similarity
        than products in different categories
        
        Returns:
            results: {
                'intra_category_similarity': float,
                'inter_category_similarity': float,
                'coherence_score': float,  # intra / inter
                'details': {...}
            }
        """
        logger.info("\n" + "="*70)
        logger.info("TEST 1: CATEGORY COHERENCE")
        logger.info("="*70)
        
        results = defaultdict(list)
        
        # Sample products from each category
        categories = self.metadata_df['category_name'].value_counts().head(10).index
        
        for category in categories:
            # Get products in this category
            cat_products = self.metadata_df[
                self.metadata_df['category_name'] == category
            ].head(sample_size)
            
            if len(cat_products) < 2:
                continue
            
            cat_ids = cat_products['variant_id'].values
            
            # Compute intra-category similarity
            intra_sims = []
            for i, id1 in enumerate(cat_ids):
                for id2 in cat_ids[i+1:]:
                    emb1 = self.get_embedding(id1)
                    emb2 = self.get_embedding(id2)
                    if emb1 is not None and emb2 is not None:
                        sim = cosine_similarity([emb1], [emb2])[0][0]
                        intra_sims.append(sim)
            
            if intra_sims:
                avg_intra = np.mean(intra_sims)
                results['intra_sims'].append(avg_intra)
                
                # Compare with random products (inter-category)
                random_products = self.metadata_df[
                    self.metadata_df['category_name'] != category
                ].sample(n=min(sample_size, len(self.metadata_df)//2))
                
                inter_sims = []
                for id1 in cat_ids[:10]:  # Sample 10 from category
                    for id2 in random_products['variant_id'].values[:10]:
                        emb1 = self.get_embedding(id1)
                        emb2 = self.get_embedding(id2)
                        if emb1 is not None and emb2 is not None:
                            sim = cosine_similarity([emb1], [emb2])[0][0]
                            inter_sims.append(sim)
                
                if inter_sims:
                    avg_inter = np.mean(inter_sims)
                    results['inter_sims'].append(avg_inter)
                    
                    logger.info(f"  {category[:30]:30s}: "
                              f"Intra={avg_intra:.3f}, Inter={avg_inter:.3f}, "
                              f"Ratio={avg_intra/avg_inter:.2f}x")
        
        # Calculate overall metrics
        intra_category_sim = np.mean(results['intra_sims'])
        inter_category_sim = np.mean(results['inter_sims'])
        coherence_score = intra_category_sim / inter_category_sim
        
        logger.info(f"\nCATEGORY COHERENCE RESULTS:")
        logger.info(f"  Intra-category similarity: {intra_category_sim:.3f}")
        logger.info(f"  Inter-category similarity: {inter_category_sim:.3f}")
        logger.info(f"  Coherence score: {coherence_score:.2f}x")
        
        # Interpretation
        if coherence_score > 1.5:
            logger.info(f"  EXCELLENT: Model strongly distinguishes categories")
        elif coherence_score > 1.2:
            logger.info(f"  GOOD: Model distinguishes categories reasonably")
        elif coherence_score > 1.0:
            logger.info(f"  WEAK: Model barely distinguishes categories")
        else:
            logger.info(f"  POOR: Model doesn't distinguish categories")
        
        return {
            'intra_category_similarity': intra_category_sim,
            'inter_category_similarity': inter_category_sim,
            'coherence_score': coherence_score,
            'details': dict(results)
        }
    
    # ========================================================================
    # TEST 2: PRICE-SIMILARITY CORRELATION
    # ========================================================================
    
    def test_price_similarity_correlation(self, sample_size: int = 100) -> Dict:
        """
        Test: Products with similar prices (within same category) 
        should have higher similarity
        
        Returns:
            results: {
                'correlation': float,
                'details': {...}
            }
        """
        logger.info("\n" + "="*70)
        logger.info("TEST 2: PRICE-SIMILARITY CORRELATION")
        logger.info("="*70)
        
        # Sample products from major categories
        major_categories = self.metadata_df['category_name'].value_counts().head(5).index
        
        price_diffs = []
        embedding_sims = []
        
        for category in major_categories:
            cat_products = self.metadata_df[
                self.metadata_df['category_name'] == category
            ].sample(n=min(sample_size, len(self.metadata_df)))
            
            if len(cat_products) < 2:
                continue
            
            # Compare pairs
            for i in range(len(cat_products)):
                for j in range(i+1, min(i+20, len(cat_products))):
                    p1 = cat_products.iloc[i]
                    p2 = cat_products.iloc[j]
                    
                    # Price difference (normalized)
                    price_diff = abs(p1['price'] - p2['price']) / max(p1['price'], p2['price'])
                    
                    # Embedding similarity
                    emb1 = self.get_embedding(p1['variant_id'])
                    emb2 = self.get_embedding(p2['variant_id'])
                    
                    if emb1 is not None and emb2 is not None:
                        sim = cosine_similarity([emb1], [emb2])[0][0]
                        
                        price_diffs.append(price_diff)
                        embedding_sims.append(sim)
        
        # Calculate correlation
        correlation = np.corrcoef(price_diffs, embedding_sims)[0, 1]
        
        logger.info(f"\nPRICE-SIMILARITY CORRELATION:")
        logger.info(f"  Correlation: {correlation:.3f}")
        
        # Interpretation
        if abs(correlation) < 0.1:
            logger.info(f"  GOOD: Embeddings are price-independent (captures style/quality)")
        elif abs(correlation) < 0.3:
            logger.info(f"  MODERATE: Some price influence")
        else:
            logger.info(f"  HIGH: Strong price bias in embeddings")
        
        return {
            'correlation': correlation,
            'num_pairs': len(price_diffs),
            'interpretation': 'price_independent' if abs(correlation) < 0.1 else 'price_biased'
        }
    
    # ========================================================================
    # TEST 3: ATTRIBUTE CONSISTENCY
    # ========================================================================
    
    def test_attribute_consistency(self) -> Dict:
        """
        Test: Products with same attributes (color, gender, size)
        should be more similar than random pairs
        """
        logger.info("\n" + "="*70)
        logger.info("TEST 3: ATTRIBUTE CONSISTENCY")
        logger.info("="*70)
        
        results = {}
        
        # Test for each attribute
        for attribute in ['color_name', 'gender', 'size']:
            if attribute not in self.metadata_df.columns:
                continue
            
            same_attr_sims = []
            diff_attr_sims = []
            
            # Sample 100 pairs
            for _ in range(100):
                # Same attribute pair
                attr_value = self.metadata_df[attribute].value_counts().index[0]
                products = self.metadata_df[self.metadata_df[attribute] == attr_value]
                
                if len(products) >= 2:
                    pair = products.sample(n=2)
                    emb1 = self.get_embedding(pair.iloc[0]['variant_id'])
                    emb2 = self.get_embedding(pair.iloc[1]['variant_id'])
                    
                    if emb1 is not None and emb2 is not None:
                        sim = cosine_similarity([emb1], [emb2])[0][0]
                        same_attr_sims.append(sim)
                
                # Different attribute pair
                diff_products = self.metadata_df[self.metadata_df[attribute] != attr_value]
                if len(diff_products) >= 1:
                    p1 = products.sample(n=1).iloc[0]
                    p2 = diff_products.sample(n=1).iloc[0]
                    
                    emb1 = self.get_embedding(p1['variant_id'])
                    emb2 = self.get_embedding(p2['variant_id'])
                    
                    if emb1 is not None and emb2 is not None:
                        sim = cosine_similarity([emb1], [emb2])[0][0]
                        diff_attr_sims.append(sim)
            
            if same_attr_sims and diff_attr_sims:
                same_avg = np.mean(same_attr_sims)
                diff_avg = np.mean(diff_attr_sims)
                ratio = same_avg / diff_avg
                
                results[attribute] = {
                    'same_attr_sim': same_avg,
                    'diff_attr_sim': diff_avg,
                    'ratio': ratio
                }
                
                logger.info(f"  {attribute:15s}: Same={same_avg:.3f}, Diff={diff_avg:.3f}, Ratio={ratio:.2f}x")
        
        return results
    
    # ========================================================================
    # TEST 4: MANUAL TEST CASES
    # ========================================================================
    
    def test_manual_cases(self, test_cases: List[Dict]) -> Dict:
        """
        Test with manually curated test cases
        
        Args:
            test_cases: [
                {
                    'anchor': variant_id,
                    'similar': [variant_id1, variant_id2],
                    'dissimilar': [variant_id3, variant_id4],
                    'description': 'test description'
                }
            ]
        
        Returns:
            results with accuracy score
        """
        logger.info("\n" + "="*70)
        logger.info("TEST 4: MANUAL TEST CASES")
        logger.info("="*70)
        
        correct = 0
        total = 0
        details = []
        
        for case in test_cases:
            anchor_id = case['anchor']
            similar_ids = case.get('similar', [])
            dissimilar_ids = case.get('dissimilar', [])
            
            anchor_emb = self.get_embedding(anchor_id)
            if anchor_emb is None:
                continue
            
            # Calculate similarities
            similar_sims = []
            for sid in similar_ids:
                emb = self.get_embedding(sid)
                if emb is not None:
                    sim = cosine_similarity([anchor_emb], [emb])[0][0]
                    similar_sims.append(sim)
            
            dissimilar_sims = []
            for did in dissimilar_ids:
                emb = self.get_embedding(did)
                if emb is not None:
                    sim = cosine_similarity([anchor_emb], [emb])[0][0]
                    dissimilar_sims.append(sim)
            
            # Check if similar > dissimilar
            if similar_sims and dissimilar_sims:
                avg_similar = np.mean(similar_sims)
                avg_dissimilar = np.mean(dissimilar_sims)
                
                is_correct = avg_similar > avg_dissimilar
                correct += is_correct
                total += 1
                
                status = "PASS" if is_correct else "FAIL"
                logger.info(f"  {status} {case.get('description', 'Test case')}: "
                          f"Similar={avg_similar:.3f}, Dissimilar={avg_dissimilar:.3f}")
                
                details.append({
                    'description': case.get('description'),
                    'correct': is_correct,
                    'similar_sim': avg_similar,
                    'dissimilar_sim': avg_dissimilar
                })
        
        accuracy = correct / total if total > 0 else 0
        
        logger.info(f"\nMANUAL TEST ACCURACY: {accuracy:.1%} ({correct}/{total})")
        
        return {
            'accuracy': accuracy,
            'correct': correct,
            'total': total,
            'details': details
        }
    
    # ========================================================================
    # TEST 5: NEAREST NEIGHBOR QUALITY
    # ========================================================================
    
    def test_nearest_neighbors(self, sample_size: int = 50, k: int = 10) -> Dict:
        """
        Test: For each product, check if top-K nearest neighbors
        share same category/attributes
        
        Returns:
            category_overlap_rate: % of neighbors in same category
        """
        logger.info("\n" + "="*70)
        logger.info("TEST 5: NEAREST NEIGHBOR QUALITY")
        logger.info("="*70)
        
        # Sample products
        sample_products = self.metadata_df.sample(n=min(sample_size, len(self.metadata_df)))
        
        category_matches = []
        color_matches = []
        gender_matches = []
        
        for _, product in sample_products.iterrows():
            anchor_emb = self.get_embedding(product['variant_id'])
            if anchor_emb is None:
                continue
            
            # Compute similarities with all products
            sims = cosine_similarity([anchor_emb], self.embeddings)[0]
            
            # Get top-K (excluding self)
            top_k_indices = np.argsort(sims)[::-1][1:k+1]
            
            # Check attribute overlap
            neighbors = self.metadata_df.iloc[top_k_indices]
            
            category_match = (neighbors['category_name'] == product['category_name']).mean()
            category_matches.append(category_match)
            
            if 'color_name' in neighbors.columns:
                color_match = (neighbors['color_name'] == product['color_name']).mean()
                color_matches.append(color_match)
            
            if 'gender' in neighbors.columns:
                gender_match = (neighbors['gender'] == product['gender']).mean()
                gender_matches.append(gender_match)
        
        results = {
            'category_overlap': np.mean(category_matches),
            'color_overlap': np.mean(color_matches) if color_matches else 0,
            'gender_overlap': np.mean(gender_matches) if gender_matches else 0
        }
        
        logger.info(f"\nNEAREST NEIGHBOR QUALITY (k={k}):")
        logger.info(f"  Category overlap: {results['category_overlap']:.1%}")
        logger.info(f"  Color overlap: {results['color_overlap']:.1%}")
        logger.info(f"  Gender overlap: {results['gender_overlap']:.1%}")
        
        # Interpretation
        if results['category_overlap'] > 0.7:
            logger.info(f"  EXCELLENT: Strong semantic clustering")
        elif results['category_overlap'] > 0.5:
            logger.info(f"  GOOD: Reasonable semantic clustering")
        else:
            logger.info(f"  POOR: Weak semantic clustering")
        
        return results
    
    # ========================================================================
    # COMPREHENSIVE EVALUATION
    # ========================================================================
    
    def run_all_tests(self, manual_test_cases: List[Dict] = None) -> Dict:
        """
        Run all evaluation tests and generate report
        
        Returns:
            comprehensive_results: Dict with all test results
        """
        logger.info("\n" + "="*80)
        logger.info(f"COMPREHENSIVE EVALUATION: {self.embedding_type} EMBEDDINGS")
        logger.info("="*80)
        
        results = {}
        
        # Run all tests
        results['category_coherence'] = self.test_category_coherence()
        results['price_correlation'] = self.test_price_similarity_correlation()
        results['attribute_consistency'] = self.test_attribute_consistency()
        results['nearest_neighbors'] = self.test_nearest_neighbors()
        
        if manual_test_cases:
            results['manual_cases'] = self.test_manual_cases(manual_test_cases)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(results)
        results['overall_score'] = overall_score
        
        # Print summary
        self._print_summary(results)
        
        return results
    
    def _calculate_overall_score(self, results: Dict) -> float:
        """Calculate weighted overall score (0-100)"""
        score = 0
        
        # Category coherence (30%)
        coherence = results['category_coherence']['coherence_score']
        score += min(coherence / 1.5, 1.0) * 30
        
        # Nearest neighbor quality (30%)
        nn_quality = results['nearest_neighbors']['category_overlap']
        score += nn_quality * 30
        
        # Attribute consistency (20%)
        attr_scores = [v['ratio'] for v in results['attribute_consistency'].values()]
        if attr_scores:
            score += min(np.mean(attr_scores) / 1.3, 1.0) * 20
        
        # Manual test cases (20%)
        if 'manual_cases' in results:
            score += results['manual_cases']['accuracy'] * 20
        else:
            score += 15  # Default partial credit
        
        return score
    
    def _print_summary(self, results: Dict):
        """Print evaluation summary"""
        logger.info("\n" + "="*80)
        logger.info("EVALUATION SUMMARY")
        logger.info("="*80)
        
        overall = results['overall_score']
        logger.info(f"\nOVERALL SCORE: {overall:.1f}/100")
        
        if overall >= 80:
            logger.info("  EXCELLENT: Model is production-ready")
            logger.info("  Recommendation: Use as-is, focus on system optimization")
        elif overall >= 65:
            logger.info("  GOOD: Model is acceptable")
            logger.info("  Recommendation: Can use in production, consider light fine-tuning")
        elif overall >= 50:
            logger.info("  FAIR: Model needs improvement")
            logger.info("  Recommendation: Fine-tune with synthetic data")
        else:
            logger.info("  POOR: Model quality is insufficient")
            logger.info("  Recommendation: Must fine-tune before production")
        
        logger.info("\nKEY METRICS:")
        logger.info(f"  - Category coherence: {results['category_coherence']['coherence_score']:.2f}x")
        logger.info(f"  - NN category overlap: {results['nearest_neighbors']['category_overlap']:.1%}")
        logger.info(f"  - Price independence: {abs(results['price_correlation']['correlation']):.3f}")
        
        logger.info("="*80)


# ============================================================================
# HELPER: CREATE MANUAL TEST CASES
# ============================================================================

def create_manual_test_cases(metadata_df: pd.DataFrame) -> List[Dict]:
    """
    Create manual test cases based on business logic
    
    Returns:
        List of test cases
    """
    test_cases = []
    
    # Example: Find products to create test cases
    # You should manually curate these based on your data
    
    # Test case 1: Same category + similar price
    category = metadata_df['category_name'].value_counts().index[0]
    cat_products = metadata_df[metadata_df['category_name'] == category]
    
    if len(cat_products) >= 5:
        # Pick anchor
        anchor = cat_products.iloc[0]
        
        # Similar: same category, similar price
        similar_products = cat_products[
            (cat_products['price'] >= anchor['price'] * 0.8) &
            (cat_products['price'] <= anchor['price'] * 1.2)
        ].head(3)
        
        # Dissimilar: different category
        dissimilar_products = metadata_df[
            metadata_df['category_name'] != category
        ].sample(n=2)
        
        test_cases.append({
            'anchor': anchor['variant_id'],
            'similar': similar_products['variant_id'].tolist(),
            'dissimilar': dissimilar_products['variant_id'].tolist(),
            'description': f'Same category ({category}) vs different'
        })
    
    return test_cases


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # Load data
    logger.info("Loading embeddings and metadata...")
    
    # Load CLIP embeddings
    clip_embeddings = np.load("../data/processed/clip_item_embeddings.npy")
    variant_ids = np.load("../data/processed/variant_ids.npy", allow_pickle=True)
    metadata_df = pd.read_csv("../data/processed/item_features.csv")
    
    # Align data
    metadata_df['variant_id'] = metadata_df['variant_id'].astype(str)
    metadata_df = metadata_df[metadata_df['variant_id'].isin(variant_ids)]
    
    # Create evaluator
    evaluator = EmbeddingQualityEvaluator(
        embeddings=clip_embeddings,
        metadata_df=metadata_df,
        embedding_type="CLIP"
    )
    
    # Create manual test cases
    manual_cases = create_manual_test_cases(metadata_df)
    
    # Run evaluation
    results = evaluator.run_all_tests(manual_test_cases=manual_cases)
    
    # Save results
    import json
    with open("../data/processed/evaluation_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info("\nEvaluation complete! Results saved to evaluation_results.json")