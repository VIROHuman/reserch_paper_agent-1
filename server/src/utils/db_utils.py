"""
Database utility functions
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import sqlite3
import json
from loguru import logger

from ..config import settings
from ..models.schemas import ReferenceData, ValidationResult


class DatabaseManager:
    """Manages database operations for reference processing"""
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or settings.database_url
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_url) as conn:
                cursor = conn.cursor()
                
                # Create references table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS references (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        original_text TEXT NOT NULL,
                        processed_data TEXT,
                        validation_result TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create processing_logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS processing_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reference_id INTEGER,
                        operation TEXT NOT NULL,
                        status TEXT NOT NULL,
                        details TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (reference_id) REFERENCES references (id)
                    )
                """)
                
                # Create api_usage table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS api_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        api_name TEXT NOT NULL,
                        endpoint TEXT NOT NULL,
                        request_count INTEGER DEFAULT 1,
                        success_count INTEGER DEFAULT 0,
                        error_count INTEGER DEFAULT 0,
                        last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
            raise
    
    def save_reference(self, original_text: str, processed_data: ReferenceData = None, 
                      validation_result: ValidationResult = None) -> int:
        """Save reference data to database"""
        try:
            with sqlite3.connect(self.db_url) as conn:
                cursor = conn.cursor()
                
                processed_json = json.dumps(processed_data.dict()) if processed_data else None
                validation_json = json.dumps(validation_result.dict()) if validation_result else None
                
                cursor.execute("""
                    INSERT INTO references (original_text, processed_data, validation_result)
                    VALUES (?, ?, ?)
                """, (original_text, processed_json, validation_json))
                
                reference_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"Saved reference with ID: {reference_id}")
                return reference_id
                
        except Exception as e:
            logger.error(f"Error saving reference: {str(e)}")
            raise
    
    def get_reference(self, reference_id: int) -> Optional[Dict[str, Any]]:
        """Get reference by ID"""
        try:
            with sqlite3.connect(self.db_url) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, original_text, processed_data, validation_result, 
                           created_at, updated_at
                    FROM references WHERE id = ?
                """, (reference_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "original_text": row[1],
                        "processed_data": json.loads(row[2]) if row[2] else None,
                        "validation_result": json.loads(row[3]) if row[3] else None,
                        "created_at": row[4],
                        "updated_at": row[5]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error getting reference: {str(e)}")
            return None
    
    def log_processing(self, reference_id: int, operation: str, status: str, details: str = None):
        """Log processing operation"""
        try:
            with sqlite3.connect(self.db_url) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO processing_logs (reference_id, operation, status, details)
                    VALUES (?, ?, ?, ?)
                """, (reference_id, operation, status, details))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error logging processing: {str(e)}")
    
    def log_api_usage(self, api_name: str, endpoint: str, success: bool = True):
        """Log API usage statistics"""
        try:
            with sqlite3.connect(self.db_url) as conn:
                cursor = conn.cursor()
                
                # Check if record exists
                cursor.execute("""
                    SELECT id, request_count, success_count, error_count
                    FROM api_usage 
                    WHERE api_name = ? AND endpoint = ?
                """, (api_name, endpoint))
                
                row = cursor.fetchone()
                
                if row:
                    # Update existing record
                    record_id, request_count, success_count, error_count = row
                    new_request_count = request_count + 1
                    new_success_count = success_count + (1 if success else 0)
                    new_error_count = error_count + (0 if success else 1)
                    
                    cursor.execute("""
                        UPDATE api_usage 
                        SET request_count = ?, success_count = ?, error_count = ?, 
                            last_used = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (new_request_count, new_success_count, new_error_count, record_id))
                else:
                    # Create new record
                    cursor.execute("""
                        INSERT INTO api_usage (api_name, endpoint, request_count, success_count, error_count)
                        VALUES (?, ?, 1, ?, ?)
                    """, (api_name, endpoint, 1 if success else 0, 0 if success else 1))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error logging API usage: {str(e)}")
    
    def get_api_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        try:
            with sqlite3.connect(self.db_url) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT api_name, endpoint, request_count, success_count, error_count, last_used
                    FROM api_usage
                    ORDER BY last_used DESC
                """)
                
                rows = cursor.fetchall()
                stats = {}
                
                for row in rows:
                    api_name, endpoint, request_count, success_count, error_count, last_used = row
                    
                    if api_name not in stats:
                        stats[api_name] = {}
                    
                    stats[api_name][endpoint] = {
                        "request_count": request_count,
                        "success_count": success_count,
                        "error_count": error_count,
                        "success_rate": success_count / request_count if request_count > 0 else 0,
                        "last_used": last_used
                    }
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting API stats: {str(e)}")
            return {}
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        try:
            with sqlite3.connect(self.db_url) as conn:
                cursor = conn.cursor()
                
                # Total references processed
                cursor.execute("SELECT COUNT(*) FROM references")
                total_references = cursor.fetchone()[0]
                
                # Processing logs by status
                cursor.execute("""
                    SELECT status, COUNT(*) 
                    FROM processing_logs 
                    GROUP BY status
                """)
                status_counts = dict(cursor.fetchall())
                
                # Recent processing activity
                cursor.execute("""
                    SELECT operation, status, created_at
                    FROM processing_logs
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                recent_activity = [
                    {"operation": row[0], "status": row[1], "created_at": row[2]}
                    for row in cursor.fetchall()
                ]
                
                return {
                    "total_references": total_references,
                    "status_counts": status_counts,
                    "recent_activity": recent_activity
                }
                
        except Exception as e:
            logger.error(f"Error getting processing stats: {str(e)}")
            return {}
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old data"""
        try:
            with sqlite3.connect(self.db_url) as conn:
                cursor = conn.cursor()
                
                # Delete old processing logs
                cursor.execute("""
                    DELETE FROM processing_logs 
                    WHERE created_at < datetime('now', '-{} days')
                """.format(days))
                
                deleted_logs = cursor.rowcount
                
                conn.commit()
                
                logger.info(f"Cleaned up {deleted_logs} old processing logs")
                return deleted_logs
                
        except Exception as e:
            logger.error(f"Error cleaning up data: {str(e)}")
            return 0