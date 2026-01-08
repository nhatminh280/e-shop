"""
Compare Pre-trained CLIP vs Fine-tuned Models
==============================================
Side-by-side comparison to decide if fine-tuning is worth it

Workflow:
1. Evaluate CLIP pretrained
2. (If you have) Evaluate CLIP fine-tuned
3. Compare metrics
4. Calculate ROI (improvement vs effort)
5. Make recommendation
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
import logging
from embedding_quality_evaluator import EmbeddingQualityEvaluator, create_manual_test_cases
import matplotlib.pyplot as plt
import seaborn as sns

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ModelComparator:
    """
    Compare multiple embedding models
    """
    
    def __init__(self, metadata_df: pd.DataFrame):
        self.metadata_df = metadata_df
        self.results = {}
    
    def evaluate_model(self, 
                      embeddings: np.ndarray,
                      model_name: str,
                      manual_test_cases: list = None) -> Dict:
        """
        Evaluate a single model
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"EVALUATING: {model_name}")
        logger.info(f"{'='*80}")
        
        evaluator = EmbeddingQualityEvaluator(
            embeddings=embeddings,
            metadata_df=self.metadata_df,
            embedding_type=model_name
        )
        
        results = evaluator.run_all_tests(manual_test_cases=manual_test_cases)
        self.results[model_name] = results
        
        return results
    
    def compare_models(self) -> pd.DataFrame:
        """
        Create comparison table
        """
        if len(self.results) < 2:
            logger.warning("Need at least 2 models to compare")
            return None
        
        comparison_data = []
        
        for model_name, results in self.results.items():
            comparison_data.append({
                'Model': model_name,
                'Overall Score': results['overall_score'],
                'Category Coherence': results['category_coherence']['coherence_score'],
                'NN Category Overlap': results['nearest_neighbors']['category_overlap'] * 100,
                'Price Correlation': abs(results['price_correlation']['correlation']),
            })
        
        df = pd.DataFrame(comparison_data)
        
        # Calculate improvements
        if len(df) == 2:
            baseline_score = df.iloc[0]['Overall Score']
            finetuned_score = df.iloc[1]['Overall Score']
            improvement = ((finetuned_score - baseline_score) / baseline_score) * 100
            
            logger.info(f"\n{'='*80}")
            logger.info("COMPARISON SUMMARY")
            logger.info(f"{'='*80}")
            logger.info(f"\nOverall Score Improvement: {improvement:+.1f}%")
            logger.info(f"  {df.iloc[0]['Model']}: {baseline_score:.1f}/100")
            logger.info(f"  {df.iloc[1]['Model']}: {finetuned_score:.1f}/100")
            
            # ROI Analysis
            self._analyze_roi(improvement)
        
        return df
    
    def _analyze_roi(self, improvement: float):
        """
        Analyze Return on Investment for fine-tuning
        """
        logger.info(f"\nROI ANALYSIS:")
        logger.info(f"{'='*80}")
        
        # Estimate effort
        estimated_effort_days = 7  # 1 week for fine-tuning
        
        if improvement > 15:
            logger.info(f"  HIGH ROI: {improvement:.1f}% improvement")
            logger.info(f"  > STRONGLY RECOMMEND fine-tuning")
            logger.info(f"  > Expected effort: ~{estimated_effort_days} days")
            logger.info(f"  > Impact: Significant quality improvement")
            recommendation = "MUST_FINETUNE"
            
        elif improvement > 5:
            logger.info(f"  MODERATE ROI: {improvement:.1f}% improvement")
            logger.info(f"  > CONSIDER fine-tuning if:")
            logger.info(f"     * You have time/resources")
            logger.info(f"     * Quality is critical for your use case")
            logger.info(f"  > Alternative: Use pretrained, optimize system")
            recommendation = "CONSIDER_FINETUNE"
            
        elif improvement > 0:
            logger.info(f"  LOW ROI: Only {improvement:.1f}% improvement")
            logger.info(f"  > NOT RECOMMENDED to fine-tune now")
            logger.info(f"  > Better to:")
            logger.info(f"     * Use pretrained model")
            logger.info(f"     * Focus on system optimization")
            logger.info(f"     * Collect interaction data first")
            recommendation = "SKIP_FINETUNE"
            
        else:
            logger.info(f"  NEGATIVE ROI: {improvement:.1f}% worse!")
            logger.info(f"  > Fine-tuning HURT performance")
            logger.info(f"  > Use pretrained model")
            recommendation = "USE_PRETRAINED"
        
        logger.info(f"{'='*80}")
        
        return recommendation
    
    def plot_comparison(self, save_path: str = None):
        """
        Visualize model comparison
        """
        if len(self.results) < 2:
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Model Comparison: Pretrained vs Fine-tuned', fontsize=16, fontweight='bold')
        
        model_names = list(self.results.keys())
        
        # 1. Overall scores
        ax = axes[0, 0]
        scores = [self.results[m]['overall_score'] for m in model_names]
        ax.bar(model_names, scores, color=['#3498db', '#e74c3c'])
        ax.set_ylabel('Overall Score', fontsize=12)
        ax.set_title('Overall Quality Score', fontsize=12, fontweight='bold')
        ax.set_ylim(0, 100)
        for i, v in enumerate(scores):
            ax.text(i, v + 2, f'{v:.1f}', ha='center', fontweight='bold')
        
        # 2. Category coherence
        ax = axes[0, 1]
        coherence = [self.results[m]['category_coherence']['coherence_score'] for m in model_names]
        ax.bar(model_names, coherence, color=['#3498db', '#e74c3c'])
        ax.set_ylabel('Coherence Score', fontsize=12)
        ax.set_title('Category Coherence (higher is better)', fontsize=12, fontweight='bold')
        ax.axhline(y=1.2, color='green', linestyle='--', label='Good threshold')
        ax.legend()
        for i, v in enumerate(coherence):
            ax.text(i, v + 0.05, f'{v:.2f}', ha='center', fontweight='bold')
        
        # 3. NN overlap rates
        ax = axes[1, 0]
        metrics = ['category_overlap', 'color_overlap', 'gender_overlap']
        x = np.arange(len(metrics))
        width = 0.35
        
        for i, model_name in enumerate(model_names):
            values = [self.results[model_name]['nearest_neighbors'].get(m, 0) * 100 for m in metrics]
            ax.bar(x + i*width, values, width, label=model_name)
        
        ax.set_ylabel('Overlap %', fontsize=12)
        ax.set_title('Nearest Neighbor Attribute Overlap', fontsize=12, fontweight='bold')
        ax.set_xticks(x + width / 2)
        ax.set_xticklabels([m.replace('_', ' ').title() for m in metrics])
        ax.legend()
        ax.set_ylim(0, 100)
        
        # 4. Metric breakdown radar
        ax = axes[1, 1]
        categories = ['Category\nCoherence', 'NN Quality', 'Attribute\nConsistency']
        
        for model_name in model_names:
            r = self.results[model_name]
            values = [
                min(r['category_coherence']['coherence_score'] / 1.5, 1.0) * 100,
                r['nearest_neighbors']['category_overlap'] * 100,
                np.mean([v['ratio'] for v in r['attribute_consistency'].values()]) / 1.3 * 100 
                    if r['attribute_consistency'] else 50
            ]
            
            angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
            values += values[:1]
            angles += angles[:1]
            
            ax = plt.subplot(2, 2, 4, projection='polar')
            ax.plot(angles, values, 'o-', linewidth=2, label=model_name)
            ax.fill(angles, values, alpha=0.25)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_ylim(0, 100)
        ax.set_title('Performance Radar', fontsize=12, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Comparison plot saved to {save_path}")
        
        plt.show()


# ============================================================================
# QUICK BASELINE TEST (without fine-tuning)
# ============================================================================

def quick_baseline_test(clip_embeddings: np.ndarray,
                       metadata_df: pd.DataFrame) -> Tuple[float, str]:
    """
    Quick test to decide if fine-tuning is needed
    
    Returns:
        (overall_score, recommendation)
    """
    logger.info("\n" + "="*80)
    logger.info("QUICK BASELINE TEST - CLIP PRETRAINED")
    logger.info("="*80)
    logger.info("This will take ~5 minutes to give you a decision...")
    
    evaluator = EmbeddingQualityEvaluator(
        embeddings=clip_embeddings,
        metadata_df=metadata_df,
        embedding_type="CLIP Pretrained"
    )
    
    # Run key tests only
    coherence = evaluator.test_category_coherence(sample_size=30)
    nn_quality = evaluator.test_nearest_neighbors(sample_size=30, k=10)
    
    # Quick score
    score = (
        min(coherence['coherence_score'] / 1.5, 1.0) * 50 +
        nn_quality['category_overlap'] * 50
    )
    
    logger.info(f"\nQUICK BASELINE SCORE: {score:.1f}/100")
    
    # Decision
    if score >= 70:
        recommendation = "USE_PRETRAINED"
        logger.info(f"\n{recommendation}")
        logger.info("  Pretrained model quality is GOOD")
        logger.info("  Recommendation: Use as-is, skip fine-tuning for now")
        logger.info("  Focus on system optimization and user experience")
        
    elif score >= 55:
        recommendation = "CONSIDER_FINETUNE"
        logger.info(f"\n{recommendation}")
        logger.info("  Pretrained model quality is ACCEPTABLE")
        logger.info("  Recommendation: Can use pretrained initially")
        logger.info("  Consider fine-tuning after collecting interaction data")
        
    else:
        recommendation = "MUST_FINETUNE"
        logger.info(f"\n{recommendation}")
        logger.info("  Pretrained model quality is INSUFFICIENT")
        logger.info("  Recommendation: Fine-tune with synthetic data before production")
        logger.info("  Expected improvement: 10-20%")
    
    logger.info("="*80)
    
    return score, recommendation


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    
    # Load data
    logger.info("Loading data...")
    
    # Load CLIP pretrained embeddings
    clip_embeddings = np.load("../data/processed/clip_item_embeddings.npy")
    variant_ids = np.load("../data/processed/variant_ids.npy", allow_pickle=True)
    metadata_df = pd.read_csv("../data/processed/item_features.csv")
    
    # Align data
    metadata_df['variant_id'] = metadata_df['variant_id'].astype(str)
    metadata_df = metadata_df[metadata_df['variant_id'].isin(variant_ids)]
    
    logger.info(f"Loaded {len(metadata_df)} products")
    
    # ========================================================================
    # OPTION 1: Quick baseline test (recommended to run first)
    # ========================================================================
    
    logger.info("\n" + "="*80)
    logger.info("RUNNING QUICK BASELINE TEST...")
    logger.info("="*80)
    
    baseline_score, recommendation = quick_baseline_test(clip_embeddings, metadata_df)
    
    # ========================================================================
    # OPTION 2: Full comparison (if you have fine-tuned model)
    # ========================================================================
    
    # Uncomment this if you have fine-tuned embeddings
    """
    logger.info("\n" + "="*80)
    logger.info("RUNNING FULL COMPARISON...")
    logger.info("="*80)
    
    # Load fine-tuned embeddings (if available)
    try:
        finetuned_embeddings = np.load("../data/processed/finetuned_clip_embeddings.npy")
        
        # Create comparator
        comparator = ModelComparator(metadata_df)
        
        # Create manual test cases
        manual_cases = create_manual_test_cases(metadata_df)
        
        # Evaluate both models
        comparator.evaluate_model(clip_embeddings, "CLIP Pretrained", manual_cases)
        comparator.evaluate_model(finetuned_embeddings, "CLIP Fine-tuned", manual_cases)
        
        # Compare
        comparison_df = comparator.compare_models()
        print("\n" + "="*80)
        print("COMPARISON TABLE")
        print("="*80)
        print(comparison_df.to_string(index=False))
        
        # Plot
        comparator.plot_comparison(save_path="../data/processed/model_comparison.png")
        
    except FileNotFoundError:
        logger.info("\nFine-tuned embeddings not found")
        logger.info("  Run fine-tuning first if baseline score is low")
    """
    
    logger.info("\nEvaluation complete!")
    logger.info(f"  Baseline score: {baseline_score:.1f}/100")
    logger.info(f"  Recommendation: {recommendation}")