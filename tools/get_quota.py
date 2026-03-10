import time
import os
import sys

# Load local path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.llm_oracle import GeminiOracle
from utils.logger import BotLogger

logger = BotLogger()
o = GeminiOracle(logger)
print("Config:", o.MODEL_CONFIGS)
print("Critical:", getattr(o, "target_critical", "None"))
print("Light:", getattr(o, "target_light", "None"))
print("Buckets:", o.buckets)
