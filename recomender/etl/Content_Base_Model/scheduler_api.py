"""
Scheduler Management APIs
Provides endpoints for monitoring scheduler status, run history, and logs
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# PYDANTIC MODELS

class TaskStatus(BaseModel):
    """Task execution status"""
    task_name: str
    last_run: Optional[str] = None
    last_status: Optional[str] = None
    last_duration: Optional[float] = None
    error_count: int = 0


class RunHistoryItem(BaseModel):
    """Single run history item"""
    task: str
    status: str
    start_time: str
    end_time: str
    duration_seconds: float
    error: Optional[str] = None


class SchedulerSummary(BaseModel):
    """Scheduler summary/KPI"""
    scheduler_running: bool
    last_full_run: Optional[str] = None
    last_full_run_status: Optional[str] = None
    total_runs_today: int
    successful_runs: int
    failed_runs: int
    average_duration_seconds: float
    next_scheduled_run: Optional[str] = None
    tasks: List[TaskStatus]


class LogEntry(BaseModel):
    """Single log entry"""
    timestamp: str
    level: str
    message: str


class SchedulerLogs(BaseModel):
    """Scheduler logs response"""
    total_entries: int
    entries: List[LogEntry]
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class RunHistoryResponse(BaseModel):
    """Run history response"""
    total_runs: int
    page: int
    page_size: int
    total_pages: int
    items: List[RunHistoryItem]


# SCHEDULER MONITOR

class SchedulerMonitor:
    """Monitor and manage scheduler data"""
    
    def __init__(self, log_dir: str = "../logs/scheduler"):
        self.log_dir = Path(log_dir)
        self.history_file = self.log_dir / "run_history.json"
        
    def get_scheduler_summary(self) -> Dict[str, Any]:
        """
        Get scheduler summary with KPIs
        
        Returns:
            Dict with scheduler status, run stats, and task info
        """
        # Load run history
        run_history = self._load_run_history()
        
        # Calculate statistics
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_runs = [r for r in run_history if datetime.fromisoformat(r.get('start_time', '')) >= today_start]
        
        successful_today = sum(1 for r in today_runs if r.get('status') == 'success')
        failed_today = sum(1 for r in today_runs if r.get('status') == 'failed')
        
        # Calculate average duration (last 10 runs)
        recent_runs = run_history[-10:]
        avg_duration = (
            sum(r.get('duration_seconds', 0) for r in recent_runs) / len(recent_runs)
            if recent_runs else 0
        )
        
        # Get last full pipeline run
        full_runs = [r for r in run_history if r.get('task') == 'ETL']
        last_full_run = full_runs[-1] if full_runs else None
        
        # Group by tasks for status
        tasks_status = self._get_tasks_status(run_history)
        
        return {
            'scheduler_running': self._is_scheduler_running(),
            'last_full_run': last_full_run.get('start_time') if last_full_run else None,
            'last_full_run_status': last_full_run.get('status') if last_full_run else None,
            'total_runs_today': len(today_runs),
            'successful_runs': successful_today,
            'failed_runs': failed_today,
            'average_duration_seconds': round(avg_duration, 2),
            'next_scheduled_run': self._get_next_scheduled_run(),
            'tasks': tasks_status
        }
    
    def get_run_history(self, 
                        page: int = 1, 
                        page_size: int = 20,
                        task_filter: Optional[str] = None,
                        status_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Get paginated run history
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            task_filter: Filter by task name
            status_filter: Filter by status (success/failed)
        
        Returns:
            Paginated run history
        """
        
        run_history = self._load_run_history()
        
        # Apply filters
        if task_filter:
            run_history = [r for r in run_history if r.get('task') == task_filter]
        
        if status_filter:
            run_history = [r for r in run_history if r.get('status') == status_filter]
        
        # Sort by start_time descending (newest first)
        run_history.sort(
            key=lambda x: datetime.fromisoformat(x.get('start_time', '1970-01-01')),
            reverse=True
        )
        
        # Paginate
        total_items = len(run_history)
        total_pages = (total_items + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        page_items = run_history[start_idx:end_idx]
        
        return {
            'total_runs': total_items,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'items': page_items
        }
    
    def get_latest_logs(self, 
                        lines: int = 100,
                        minutes: Optional[int] = None) -> Dict[str, Any]:
        """
        Get latest scheduler logs
        
        Args:
            lines: Number of log lines to return
            minutes: Filter logs from last N minutes
        
        Returns:
            Log entries with metadata
        """
        # Find latest log file
        log_files = sorted(self.log_dir.glob("scheduler_*.log"), reverse=True)
        
        if not log_files:
            return {
                'total_entries': 0,
                'entries': [],
                'start_time': None,
                'end_time': None
            }
        
        log_file = log_files[0]
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            return {
                'total_entries': 0,
                'entries': [],
                'error': str(e)
            }
        
        # Parse log lines
        entries = []
        cutoff_time = None
        if minutes:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        for line in reversed(all_lines[-lines:]):
            try:
                entry = self._parse_log_line(line, cutoff_time)
                if entry:
                    entries.append(entry)
            except Exception as e:
                logger.debug(f"Could not parse log line: {e}")
        
        # Reverse to get chronological order
        entries.reverse()
        
        return {
            'total_entries': len(entries),
            'entries': entries,
            'start_time': entries[0].get('timestamp') if entries else None,
            'end_time': entries[-1].get('timestamp') if entries else None,
            'log_file': str(log_file)
        }
    
    def get_task_status(self, task_name: str) -> Dict[str, Any]:
        """
        Get detailed status of a specific task
        
        Args:
            task_name: Name of the task
        
        Returns:
            Task status with recent runs
        """
        run_history = self._load_run_history()
        task_runs = [r for r in run_history if r.get('task') == task_name]
        
        if not task_runs:
            return {
                'task_name': task_name,
                'status': 'not_run',
                'recent_runs': [],
                'success_rate': 0.0,
                'last_run': None
            }
        
        # Calculate success rate (last 10 runs)
        recent = task_runs[-10:]
        successful = sum(1 for r in recent if r.get('status') == 'success')
        success_rate = (successful / len(recent)) * 100 if recent else 0
        
        return {
            'task_name': task_name,
            'status': task_runs[-1].get('status'),
            'recent_runs': recent[-5:],  # Last 5 runs
            'success_rate': round(success_rate, 2),
            'last_run': task_runs[-1].get('start_time'),
            'total_runs': len(task_runs),
            'total_duration_seconds': sum(r.get('duration_seconds', 0) for r in task_runs),
            'average_duration_seconds': round(
                sum(r.get('duration_seconds', 0) for r in task_runs) / len(task_runs),
                2
            )
        }
    
    def get_scheduler_stats(self) -> Dict[str, Any]:
        """Get overall scheduler statistics"""
        run_history = self._load_run_history()
        
        if not run_history:
            return {
                'total_runs': 0,
                'total_successful': 0,
                'total_failed': 0,
                'success_rate': 0.0,
                'total_duration_hours': 0.0,
                'average_duration_minutes': 0.0
            }
        
        successful = sum(1 for r in run_history if r.get('status') == 'success')
        failed = sum(1 for r in run_history if r.get('status') == 'failed')
        total_duration = sum(r.get('duration_seconds', 0) for r in run_history)
        
        return {
            'total_runs': len(run_history),
            'total_successful': successful,
            'total_failed': failed,
            'success_rate': round((successful / len(run_history)) * 100, 2) if run_history else 0,
            'total_duration_hours': round(total_duration / 3600, 2),
            'average_duration_minutes': round(total_duration / len(run_history) / 60, 2) if run_history else 0,
            'oldest_run': run_history[0].get('start_time') if run_history else None,
            'latest_run': run_history[-1].get('start_time') if run_history else None
        }
    
    
    # Helper Methods
    
    def _load_run_history(self) -> List[Dict]:
        """Load run history from file"""
        if not self.history_file.exists():
            return []
        
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading run history: {e}")
            return []
    
    def _get_tasks_status(self, run_history: List[Dict]) -> List[Dict]:
        """Extract task status from run history"""
        tasks_status = {}
        
        for run in run_history:
            task = run.get('task')
            if task not in tasks_status:
                tasks_status[task] = {
                    'task_name': task,
                    'last_run': None,
                    'last_status': None,
                    'last_duration': None,
                    'error_count': 0
                }
            
            # Update with latest run
            if not tasks_status[task]['last_run']:
                tasks_status[task]['last_run'] = run.get('start_time')
                tasks_status[task]['last_status'] = run.get('status')
                tasks_status[task]['last_duration'] = run.get('duration_seconds')
            
            if run.get('status') == 'failed':
                tasks_status[task]['error_count'] += 1
        
        return list(tasks_status.values())
    
    def _is_scheduler_running(self) -> bool:
        """Check if scheduler is running"""
        # Check if scheduler container is running
        import subprocess
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=eshop-scheduler", "--format", "{{.ID}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return len(result.stdout.strip()) > 0
        except Exception as e:
            logger.debug(f"Could not check scheduler status: {e}")
            return False
    
    def _get_next_scheduled_run(self) -> Optional[str]:
        """Get next scheduled run time"""
        # This would read from scheduler configuration
        try:
            config_path = Path("scheduler_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Get ETL schedule time
                if config.get('etl', {}).get('enabled'):
                    schedule_time = config['etl'].get('time', '02:00')
                    today = datetime.now().date()
                    scheduled_dt = datetime.combine(today, datetime.strptime(schedule_time, '%H:%M').time())
                    
                    # If time has passed today, schedule for tomorrow
                    if scheduled_dt <= datetime.now():
                        scheduled_dt += timedelta(days=1)
                    
                    return scheduled_dt.isoformat()
        except Exception as e:
            logger.debug(f"Could not get next scheduled run: {e}")
        
        return None
    
    def _parse_log_line(self, line: str, cutoff_time: Optional[datetime] = None) -> Optional[Dict]:
        """
        Parse log line to extract timestamp, level, and message
        Expected format: [timestamp] - [logger] - [level] - [message]
        """
        try:
            # Example: 2024-11-22 10:30:45,123 - scheduler - INFO - Starting task
            parts = line.strip().split(' - ', 3)
            if len(parts) < 4:
                return None
            
            timestamp_str = parts[0]
            # level = parts[2]
            message = parts[3]
            
            # Parse timestamp
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
            except ValueError:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            
            # Apply cutoff filter
            if cutoff_time and timestamp < cutoff_time:
                return None
            
            # Extract log level
            level = 'INFO'
            if 'ERROR' in line.upper():
                level = 'ERROR'
            elif 'WARNING' in line.upper():
                level = 'WARNING'
            elif 'DEBUG' in line.upper():
                level = 'DEBUG'
            
            return {
                'timestamp': timestamp.isoformat(),
                'level': level,
                'message': message[:500]  # Limit message length
            }
        except Exception as e:
            logger.debug(f"Error parsing log line: {e}")
            return None



# Initialize Monitor


_monitor: Optional[SchedulerMonitor] = None

def get_scheduler_monitor() -> SchedulerMonitor:
    """Get or create scheduler monitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = SchedulerMonitor()
    return _monitor