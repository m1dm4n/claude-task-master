import sys
import os

# Add the project root directory (which contains the 'src' folder) to the Python path
# This allows pytest to find modules in 'src' using 'from src.module import ...'
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)