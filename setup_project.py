import os
import sys
from pathlib import Path

def create_directory_structure():
    base_dir = Path("arbitrage_system")
    
    # Main directories
    directories = [
        base_dir,
        base_dir / "app",
        base_dir / "tests",
        base_dir / "config",
        base_dir / "logs",
        base_dir / "scripts",
        # App subdirectories
        base_dir / "app" / "api",
        base_dir / "app" / "core",
        base_dir / "app" / "data",
        base_dir / "app" / "marketplaces",
        base_dir / "app" / "models",
        base_dir / "app" / "notifications",
        base_dir / "app" / "services",
        base_dir / "app" / "tasks",
        base_dir / "app" / "utils",
        base_dir / "app" / "web",
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")

    # Create necessary __init__.py files
    init_locations = [
        base_dir / "app",
        base_dir / "app" / "api",
        base_dir / "app" / "core",
        base_dir / "app" / "data",
        base_dir / "app" / "marketplaces",
        base_dir / "app" / "models",
        base_dir / "app" / "notifications",
        base_dir / "app" / "services",
        base_dir / "app" / "tasks",
        base_dir / "app" / "utils",
        base_dir / "app" / "web",
    ]

    for location in init_locations:
        init_file = location / "__init__.py"
        init_file.touch()
        print(f"Created __init__.py in: {location}")

if __name__ == "__main__":
    create_directory_structure() 