"""Logging configuration for Phase 2 processing."""

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)

def get_logger(name: str = 'phase2') -> logging.Logger:
    return logging.getLogger(name)
