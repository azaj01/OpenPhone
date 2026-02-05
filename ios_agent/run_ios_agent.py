#!/usr/bin/env python3
"""
iOS Agent Runner for Android-Lab

This script uses Android-Lab's framework to run iOS automation tasks.
It follows the pattern from evaluation.py, simplified to only use local_agent.

Usage:
    python ios_agent/run_ios_agent.py --wda-url http://localhost:8100 --task "Open Safari and search for iPhone tips"
"""

import argparse
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import Android-Lab modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from ios_agent.connection import IOSConnection
from ios_agent.controller import IOSController
from ios_agent.executor import IOSExecutor
from ios_agent.task import IOSTask
from ios_agent.recorder import IOSRecorder
from utils_mobile.utils import print_with_color


class IOSConfig:
    """Simple config class for iOS agent."""
    def __init__(self, task_dir=None, screenshot_dir=None):
        self.task_dir = task_dir or "./ios_logs"
        self.screenshot_dir = screenshot_dir or os.path.join(self.task_dir, "screenshots")


def main():
    parser = argparse.ArgumentParser(
        description="iOS Agent Runner for Android-Lab",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--wda-url",
        type=str,
        default=os.getenv("WDA_URL", "http://localhost:8100"),
        help="WebDriverAgent URL",
    )

    parser.add_argument(
        "--task",
        type=str,
        required=True,
        help="Task to execute",
    )

    parser.add_argument(
        "--max-rounds",
        type=int,
        default=50,
        help="Maximum number of rounds",
    )

    parser.add_argument(
        "--task-dir",
        type=str,
        default=None,
        help="Directory to save task logs and screenshots",
    )

    parser.add_argument(
        "--request-interval",
        type=float,
        default=2.0,
        help="Interval between requests (seconds)",
    )

    args = parser.parse_args()

    # Initialize iOS connection
    print("🔍 Checking iOS connection...")
    conn = IOSConnection(wda_url=args.wda_url)

    if not conn.is_wda_ready():
        print(f"❌ WebDriverAgent is not ready at {args.wda_url}")
        print("Please make sure WebDriverAgent is running on your iOS device.")
        sys.exit(1)

    print("✅ WebDriverAgent is ready")

    # Start WDA session
    success, session_id = conn.start_wda_session()
    if not success:
        print(f"❌ Failed to start WDA session: {session_id}")
        sys.exit(1)

    print(f"✅ Started WDA session: {session_id}")

    # Create task ID first (needed for screenshot_dir)
    task_id = f"ios_task_{int(time.time())}"
    demo_timestamp = int(time.time())
    task_name = task_id + "_" + datetime.fromtimestamp(demo_timestamp).strftime("%Y-%m-%d_%H-%M-%S")

    # Setup config (needed for screenshot_dir)
    config = IOSConfig(
        task_dir=args.task_dir or f"./ios_logs/{task_name}",
        screenshot_dir=os.path.join(args.task_dir or f"./ios_logs/{task_name}", "screenshots")
    )
    os.makedirs(config.task_dir, exist_ok=True)
    os.makedirs(config.screenshot_dir, exist_ok=True)

    # Initialize controller
    controller = IOSController(wda_url=args.wda_url, session_id=session_id)
    # Set controller screenshot_dir to match executor (for consistency)
    controller.screenshot_dir = config.screenshot_dir

    # Initialize executor with screenshot_dir from config
    executor = IOSExecutor(wda_url=args.wda_url, session_id=session_id)
    executor.screenshot_dir = config.screenshot_dir

    # Initialize agent (using Android-Lab's agent framework)
    # Note: Agent should be initialized from Android-Lab's agent configuration
    # This is a placeholder - actual agent initialization should follow Android-Lab's pattern
    from agent.model import QwenVLAgent, OpenAIAgent
    
    # Check which agent type to use (default to OpenAIAgent for better compatibility)
    agent_type = os.getenv("AGENT_TYPE", "OpenAIAgent").strip()
    
    # For local_agent, API_KEY is not required (can be empty or "EMPTY")
    # Use default values matching Android-Lab's local_agent configuration
    api_key = os.getenv("API_KEY", "EMPTY")
    api_base = os.getenv("API_BASE", "http://localhost:8002/v1")
    model_name = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-3B-Instruct")
    
    # Validate required environment variables (API_KEY is optional for local_agent)
    if not api_base or not model_name:
        print("⚠️  Warning: Missing required environment variables:")
        if not api_base:
            print("   - API_BASE")
        if not model_name:
            print("   - MODEL_NAME")
        print("\nPlease set these environment variables before running:")
        print("   export API_BASE='your_api_base'")
        print("   export MODEL_NAME='your_model_name'")
        print("\nFor local_agent (default configuration):")
        print("   export API_BASE='http://localhost:8002/v1'")
        print("   export MODEL_NAME='Qwen/Qwen2.5-3B-Instruct'")
        print("\nNote: API_KEY is optional for local_agent (defaults to 'EMPTY')")
        sys.exit(1)
    
    # Initialize agent based on type
    if agent_type == "QwenVLAgent":
        agent = QwenVLAgent(
            api_key=api_key,
            api_base=api_base,
            model_name=model_name,
        )
    else:
        # Default to OpenAIAgent (has prompt_to_message_visual method)
        agent = OpenAIAgent(
            api_key=api_key,
            api_base=api_base,
            model_name=model_name,
        )

    # Config is already set up above, no need to recreate it

    # Initialize recorder
    record = IOSRecorder(
        id=task_name,
        instruction=args.task,
        page_executor=executor,
        config=config
    )

    # Initialize task
    task_agent = IOSTask(
        instruction=args.task,
        controller=controller,
        page_executor=executor,
        agent=agent,
        record=record,
        command_per_step=None
    )

    print_with_color(f"\n📱 Task: {args.task}\n", "green")
    print("=" * 50)

    round_count = 0
    task_complete = False

    while round_count < args.max_rounds:
        try:
            round_count += 1
            print_with_color(f"Round {round_count}", "yellow")
            task_agent.run_step(round_count - 1)  # round_count is 0-indexed in run_step
            print_with_color("Thinking about what to do in the next step...", "yellow")
            time.sleep(args.request_interval)

            if task_agent.page_executor.is_finish:
                print_with_color(f"Completed successfully.", "green")
                task_agent.page_executor.update_screenshot(prefix="end")
                task_complete = True
                break
        except Exception as e:
            import traceback
            print(traceback.print_exc())
            print_with_color(f"Error: {e}", "red")
            break

    print("\n" + "=" * 50)
    if task_complete:
        print_with_color("✅ Task completed!", "green")
    else:
        print_with_color("❌ Task incomplete or failed", "red")


if __name__ == "__main__":
    main()
