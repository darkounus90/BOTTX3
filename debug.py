import traceback
import sys

def debug():
    try:
        from main import TX3ProBot
        bot = TX3ProBot(phase=1, dry_run=True)
        bot.run()
    except Exception as e:
        print(traceback.format_exc())

debug()
