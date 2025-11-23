"""
Automated Scheduler for E-commerce Recommendation Pipeline
===========================================================

Features:
- Scheduled ETL jobs (daily, weekly, or custom intervals)
- Automatic CLIP embedding generation
- BERT metadata embedding
- Hybrid embedding fusion
- FAISS index rebuilding
- Health monitoring and notifications
- Logging and error handling

Usage:
    # Run once
    python3 scheduler.py --run-once
    
    # Run as daemon with schedule
    python3 scheduler.py --daemon
    
    # Run specific task
    python3 scheduler.py --task etl
    python3 scheduler.py --task embeddings
    python3 scheduler.py --task build-index
"""

import schedule
import time
import logging
import argparse
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import json
import traceback
import subprocess
import psutil

from config import Config
from etl_pipeline import ETLPipeline
from clip_embedding_pipeline import ClipEmbeddingPipeline
from run_etl import run_full_etl_pipeline

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(log_dir: str = "logs/scheduler") -> logging.Logger:
    """Setup logging configuration"""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    log_file = Path(log_dir) / f"scheduler_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger("scheduler")
    return logger

logger = setup_logging()

# PIPELINE TASKS


class PipelineTask:
    """Base class for pipeline tasks"""
    
    def __init__(self, name: str):
        self.name = name
        self.last_run = None
        self.last_status = None
        self.last_duration = None
        self.error_count = 0
        
    def execute(self) -> Dict[str, Any]:
        """Execute task - to be implemented by subclasses"""
        raise NotImplementedError
    
    def run(self) -> Dict[str, Any]:
        """Run task with error handling and logging"""
        logger.info("="*70)
        logger.info(f"Starting task: {self.name}")
        logger.info("="*70)
        
        start_time = time.time()
        result = {
            'task': self.name,
            'start_time': datetime.now().isoformat(),
            'status': 'failed',
            'error': None
        }
        
        try:
            task_result = self.execute()
            result.update(task_result)
            result['status'] = 'success'
            self.last_status = 'success'
            self.error_count = 0
            
            logger.info(f"Task '{self.name}' completed successfully")
            
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            result['error'] = error_msg
            result['status'] = 'failed'
            self.last_status = 'failed'
            self.error_count += 1
            
            logger.error(f"Task '{self.name}' failed: {e}")
            logger.error(traceback.format_exc())
            
        finally:
            duration = time.time() - start_time
            result['duration_seconds'] = duration
            result['end_time'] = datetime.now().isoformat()
            
            self.last_run = datetime.now()
            self.last_duration = duration
            
            logger.info(f"Task duration: {duration:.2f}s")
            logger.info("="*70)
            
        return result


class ETLTask(PipelineTask):
    """ETL Task: Extract, Transform, Load data"""
    
    def __init__(self, lookback_days: int = None):
        super().__init__("ETL")
        self.lookback_days = lookback_days or Config.LOOKBACK_DAYS
    
    def execute(self) -> Dict[str, Any]:
        logger.info(f"Running ETL with lookback_days={self.lookback_days}")
        
        # Run full ETL pipeline (includes image download and mapping)
        result = run_full_etl_pipeline(
            lookback_days=self.lookback_days,
            overwrite=False  # Don't re-download existing images
        )
        
        return {
            'interactions_count': len(result['interactions']),
            'users_count': len(result['user_features']),
            'items_count': len(result['item_features'])
        }


class CLIPEmbeddingTask(PipelineTask):
    """CLIP Embedding Generation Task"""
    
    def __init__(self, text_weight: float = 0.5):
        super().__init__("CLIP_Embedding")
        self.text_weight = text_weight
    
    def execute(self) -> Dict[str, Any]:
        logger.info(f"Generating CLIP embeddings (text_weight={self.text_weight})")
        
        pipeline = ClipEmbeddingPipeline(
            db_config=Config.DB_CONFIG,
            model_name="ViT-B/32",
            text_weight=self.text_weight
        )
        
        pipeline.run(save_to_db=True, save_to_numpy=True)
        
        # Get embedding count
        import numpy as np
        embeddings = np.load("./data/processed/clip_item_embeddings.npy")
        
        return {
            'embeddings_count': len(embeddings),
            'embedding_dim': embeddings.shape[1]
        }


class BERTHybridTask(PipelineTask):
    """BERT Metadata + Hybrid Embedding Task"""
    
    def __init__(self, fusion_alpha: float = 0.7):
        super().__init__("BERT_Hybrid")
        self.fusion_alpha = fusion_alpha
    
    def execute(self) -> Dict[str, Any]:
        logger.info(f"Generating BERT metadata + Hybrid embeddings (alpha={self.fusion_alpha})")
        
        from Content_Base_Model.bert_metadata_embedder import HybridEmbeddingPipeline
        
        pipeline = HybridEmbeddingPipeline(
            db_config=Config.DB_CONFIG,
            bert_model="bert-base-uncased",
            fusion_alpha=self.fusion_alpha,
            device="cuda"
        )
        
        results = pipeline.run(
            save_to_db=True,
            save_to_numpy=True,
            input_dir="./data/processed",
            output_dir="./data/processed"
        )
        
        return {
            'hybrid_embeddings_count': len(results['hybrid_embeddings']),
            'embedding_dim': results['hybrid_embeddings'].shape[1]
        }


class FAISSIndexTask(PipelineTask):
    """FAISS Index Building Task"""
    
    def __init__(self):
        super().__init__("FAISS_Index")
    
    def execute(self) -> Dict[str, Any]:
        logger.info("Building FAISS index from hybrid embeddings")
        
        # Run FAISS index builder
        result = subprocess.run(
            [sys.executable, "./Content_Base_Model/faiss_api.py", "build-index"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FAISS index build failed:\n{result.stderr}")
        
        # Kiểm tra file index tồn tại
        index_path = "./data/faiss/hybrid_index.faiss"
        if not Path(index_path).exists():
            raise RuntimeError(f"FAISS index was not created at {index_path}")
        
        # Load embeddings chỉ để trả số lượng
        import numpy as np
        embeddings = np.load("./data/processed/hybrid_embeddings.npy")
        
        return {
            'index_size': len(embeddings),
            'index_path': index_path
        }


class HealthCheckTask(PipelineTask):
    """System Health Check Task"""
    
    def __init__(self):
        super().__init__("HealthCheck")
    
    def execute(self) -> Dict[str, Any]:
        logger.info("Running system health check")
        
        health = {
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }
        
        # Check data files
        required_files = [
            "./data/processed/interactions.csv",
            "./data/processed/user_features.csv",
            "./data/processed/item_features.csv",
            "./data/processed/clip_item_embeddings.npy",
            "./data/processed/hybrid_embeddings.npy",
            "./data/faiss/hybrid_index.faiss"
        ]
        
        for file in required_files:
            health['checks'][file] = Path(file).exists()
        
        # Check database connection
        try:
            import psycopg2
            conn = psycopg2.connect(**Config.DB_CONFIG)
            conn.close()
            health['checks']['database'] = True
        except:
            health['checks']['database'] = False
        
        # Check disk space
        disk_usage = psutil.disk_usage('/')
        health['disk_usage_percent'] = disk_usage.percent
        health['disk_free_gb'] = disk_usage.free / (1024**3)
        
        # Check memory
        memory = psutil.virtual_memory()
        health['memory_usage_percent'] = memory.percent
        health['memory_available_gb'] = memory.available / (1024**3)
        
        all_healthy = all(health['checks'].values())
        health['status'] = 'healthy' if all_healthy else 'unhealthy'
        
        return health


# ============================================================================
# PIPELINE SCHEDULER
# ============================================================================

class PipelineScheduler:
    """Main scheduler for recommendation pipeline"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self.default_config()
        self.tasks = {}
        self.running = False
        self.run_history = []
        
        # Setup tasks
        self.setup_tasks()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
    
    def default_config(self) -> Dict[str, Any]:
        """Default scheduler configuration"""
        return {
            'etl': {
                'enabled': True,
                'schedule': 'daily',
                'time': '02:00',  # 2 AM
                'lookback_days': 90
            },
            'clip_embedding': {
                'enabled': True,
                'schedule': 'after_etl',  # Run after ETL
                'text_weight': 0.5
            },
            'bert_hybrid': {
                'enabled': True,
                'schedule': 'after_clip',  # Run after CLIP
                'fusion_alpha': 0.7
            },
            'faiss_index': {
                'enabled': True,
                'schedule': 'after_bert',  # Run after BERT
            },
            'health_check': {
                'enabled': True,
                'schedule': 'hourly',
            }
        }
    
    def setup_tasks(self):
        """Setup all pipeline tasks"""
        # ETL Task
        if self.config['etl']['enabled']:
            self.tasks['etl'] = ETLTask(
                lookback_days=self.config['etl']['lookback_days']
            )
        
        # CLIP Embedding Task
        if self.config['clip_embedding']['enabled']:
            self.tasks['clip_embedding'] = CLIPEmbeddingTask(
                text_weight=self.config['clip_embedding']['text_weight']
            )
        
        # BERT Hybrid Task
        if self.config['bert_hybrid']['enabled']:
            self.tasks['bert_hybrid'] = BERTHybridTask(
                fusion_alpha=self.config['bert_hybrid']['fusion_alpha']
            )
        
        # FAISS Index Task
        if self.config['faiss_index']['enabled']:
            self.tasks['faiss_index'] = FAISSIndexTask()
        
        # Health Check Task
        if self.config['health_check']['enabled']:
            self.tasks['health_check'] = HealthCheckTask()
        
        logger.info(f"Initialized {len(self.tasks)} tasks: {list(self.tasks.keys())}")
    
    def run_task(self, task_name: str) -> Dict[str, Any]:
        """Run a specific task"""
        if task_name not in self.tasks:
            raise ValueError(f"Task '{task_name}' not found")
        
        task = self.tasks[task_name]
        result = task.run()
        
        # Save to history
        self.run_history.append(result)
        self.save_history()
        
        return result
    
    def run_full_pipeline(self):
        """Run complete pipeline: ETL -> CLIP -> BERT -> FAISS"""
        logger.info("Starting FULL PIPELINE")
        
        pipeline_tasks = ['etl', 'clip_embedding', 'bert_hybrid', 'faiss_index']
        results = {}
        
        for task_name in pipeline_tasks:
            if task_name not in self.tasks:
                logger.warning(f"Skipping disabled task: {task_name}")
                continue
            
            result = self.run_task(task_name)
            results[task_name] = result
            
            if result['status'] == 'failed':
                logger.error(f"Pipeline stopped due to failure in task: {task_name}")
                break
        
        logger.info("FULL PIPELINE COMPLETED")
        return results
    
    def setup_schedules(self):
        """Setup scheduled jobs"""
        # ETL Schedule
        if self.config['etl']['enabled']:
            schedule_time = self.config['etl']['time']
            if self.config['etl']['schedule'] == 'daily':
                schedule.every().day.at(schedule_time).do(self.run_full_pipeline)
                logger.info(f"ETL scheduled daily at {schedule_time}")
            elif self.config['etl']['schedule'] == 'weekly':
                schedule.every().monday.at(schedule_time).do(self.run_full_pipeline)
                logger.info(f"ETL scheduled weekly (Monday) at {schedule_time}")
        
        # Health Check Schedule
        if self.config['health_check']['enabled']:
            if self.config['health_check']['schedule'] == 'hourly':
                schedule.every().hour.do(self.run_task, 'health_check')
                logger.info("Health check scheduled hourly")
    
    def start_daemon(self):
        """Start scheduler daemon"""
        logger.info("Starting Pipeline Scheduler Daemon")
        logger.info(f"Configuration: {json.dumps(self.config, indent=2)}")
        
        self.setup_schedules()
        self.running = True
        
        logger.info("Scheduler is running. Press Ctrl+C to stop.")
        
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            self.shutdown()
    
    def shutdown(self, signum=None, frame=None):
        """Graceful shutdown"""
        logger.info("Shutting down scheduler...")
        self.running = False
        self.save_history()
        logger.info("Scheduler stopped")
        sys.exit(0)
    
    def save_history(self):
        """Save run history to file"""
        history_file = Path("logs/scheduler/run_history.json")
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(history_file, 'w') as f:
            json.dump(self.run_history[-1000:], f, indent=2)  # Keep last 1000 runs
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        status = {
            'running': self.running,
            'tasks': {},
            'next_runs': []
        }
        
        for task_name, task in self.tasks.items():
            status['tasks'][task_name] = {
                'last_run': task.last_run.isoformat() if task.last_run else None,
                'last_status': task.last_status,
                'last_duration': task.last_duration,
                'error_count': task.error_count
            }
        
        # Get next scheduled runs
        for job in schedule.jobs:
            status['next_runs'].append({
                'job': str(job.job_func),
                'next_run': job.next_run.isoformat() if job.next_run else None
            })
        
        return status


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Recommendation Pipeline Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run full pipeline once
    python scheduler.py --run-once
    
    # Run specific task
    python scheduler.py --task etl
    python scheduler.py --task clip_embedding
    python scheduler.py --task health_check
    
    # Start scheduler daemon
    python scheduler.py --daemon
    
    # Custom schedule configuration
    python scheduler.py --daemon --config custom_schedule.json
        """
    )
    
    parser.add_argument('--run-once', action='store_true',
                       help='Run full pipeline once and exit')
    parser.add_argument('--task', type=str,
                       help='Run specific task: etl, clip_embedding, bert_hybrid, faiss_index, health_check')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon with scheduled jobs')
    parser.add_argument('--config', type=str,
                       help='Path to custom configuration JSON file')
    parser.add_argument('--status', action='store_true',
                       help='Show scheduler status')
    
    args = parser.parse_args()
    
    # Load custom config if provided
    config = None
    if args.config:
        with open(args.config) as f:
            config = json.load(f)
    
    scheduler = PipelineScheduler(config)
    
    if args.run_once:
        # Run full pipeline once
        results = scheduler.run_full_pipeline()
        print("\n" + "="*70)
        print("PIPELINE RESULTS")
        print("="*70)
        print(json.dumps(results, indent=2))
        
    elif args.task:
        # Run specific task
        result = scheduler.run_task(args.task)
        print("\n" + "="*70)
        print(f"TASK RESULT: {args.task}")
        print("="*70)
        print(json.dumps(result, indent=2))
        
    elif args.status:
        # Show status
        status = scheduler.get_status()
        print("\n" + "="*70)
        print("SCHEDULER STATUS")
        print("="*70)
        print(json.dumps(status, indent=2))
        
    elif args.daemon:
        # Start daemon
        scheduler.start_daemon()
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
