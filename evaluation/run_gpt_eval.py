import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from evaluation.base_eval import main

MODEL = "gpt-4.1-mini"


if __name__ == "__main__":
    main([MODEL])
