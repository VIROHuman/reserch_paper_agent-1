#!/usr/bin/env python3
"""
Run the Simplified Research Paper Reference Agent API server
"""
import uvicorn
from server.src.api.main_simple import app

if __name__ == "__main__":
    uvicorn.run(
        "server.src.api.main_simple:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
