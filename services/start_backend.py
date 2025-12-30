#!/usr/bin/env python3
"""
Wrapper script to load .env and start the backend
This ensures environment variables are loaded before FastAPI starts
"""
import os
import subprocess
import sys
from pathlib import Path

# Change to backend directory
backend_dir = Path("/Users/tomasruiz/Desktop/Fuel-Analytics-Backend")
os.chdir(backend_dir)

# Load .env file
env_file = backend_dir / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes
                value = value.strip('"').strip("'")
                os.environ[key.strip()] = value

# Set Python path
os.environ["PYTHONPATH"] = str(backend_dir)
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["DEV_MODE"] = "false"

# Run main.py using subprocess
python_path = "/opt/anaconda3/bin/python"
main_py = str(backend_dir / "main.py")

# Execute main.py and let it run
os.execv(python_path, [python_path, main_py])
