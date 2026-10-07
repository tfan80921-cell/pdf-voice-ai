#!/usr/bin/env python3
"""
Production entry point.
Usage:
    python run.py
    # or
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
"""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
        workers=1,  # ChromaDB + sentence-transformers are not multi-process safe by default
    )
