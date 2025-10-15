#!/usr/bin/env python3
"""
Research Paper Reference Agent - Server Launcher
Runs the FastAPI backend server
"""

import os
import sys
import subprocess
from loguru import logger

if __name__ == "__main__":
    logger.info("🚀 Starting Research Paper Reference Agent API Server")
    logger.info("📍 Server will be available at: http://localhost:8000")
    logger.info("📚 API Documentation: http://localhost:8000/docs")
    
    try:
        # Change to server directory
        server_dir = os.path.join(os.path.dirname(__file__), "server")
        os.chdir(server_dir)
        
        # Run uvicorn directly using subprocess
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "src.api.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--log-level", "info"
        ])
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        logger.exception(e)
        sys.exit(1)


