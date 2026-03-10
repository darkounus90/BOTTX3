import os
import json
import logging
import sys

# Add current path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.logger import BotLogger
from core.llm_oracle import GeminiOracle

logger = BotLogger()
o = GeminiOracle(logger)

try:
    reasoning = "TEST_VETO: Comprar en máximo histórico indiscutible después de 5 velas verdes gigantes y RSI en 95. Estructura rompiendo a la baja masivamente."
    print("Testing Evaluate Trade:")
    result = o.evaluate_trade("EURUSD", "BUY", reasoning, 85.0)
    print("RESULT:", result)
except Exception as e:
    print(f"Error test script: {e}")
