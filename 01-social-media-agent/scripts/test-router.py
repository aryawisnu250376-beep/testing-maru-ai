"""Tahap 1: satu pertanyaan tes harus dijawab model lewat 9Router."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import router9
print(json.dumps(router9.test_question(), ensure_ascii=False, indent=2))
