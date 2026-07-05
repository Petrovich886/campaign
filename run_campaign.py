import asyncio
import os
import sys
import argparse
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))
from promo_engine import run_campaign

API_ID = 19839869
API_HASH = "7963a733802269d97dcb2234604f5801"

def logger(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode('utf-8'), flush=True)

async def main():
    parser = argparse.ArgumentParser(description="Synthesis Promo Campaign")
    parser.add_argument("--mode", choices=["chat", "dialogue"], default="chat",
                        help="chat: respond to real messages (default), dialogue: scripted Q&A")
    args = parser.parse_args()

    stop_event = asyncio.Event()
    logger(f"Starting campaign in '{args.mode}' mode...")
    await run_campaign(API_ID, API_HASH, logger, stop_event, mode=args.mode)

if __name__ == "__main__":
    asyncio.run(main())
