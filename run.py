#!/usr/bin/env python3
"""
Startup script for running the FastAPI application.
This is used for Railway deployment.
"""
import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import uvicorn
from endpoints.config import get_api_config

if __name__ == "__main__":
    api_config = get_api_config()
    
    # Railway provides PORT environment variable
    port = int(os.getenv("PORT", api_config["port"]))
    host = api_config["host"]
    
    # Use string import path so uvicorn can properly resolve the app
    uvicorn.run(
        "endpoints.main:app",
        host=host,
        port=port,
        reload=api_config["reload"],
        log_level="info"
    )

