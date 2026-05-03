import sys
from pathlib import Path

# Make project root importable in all test files
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))
