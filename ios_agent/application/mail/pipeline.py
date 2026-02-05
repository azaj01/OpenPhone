#!/usr/bin/env python3
"""
Mail Pipeline for iOS Agent

Task: Open Mail app, locate the inbox/mail list, and sequentially open the five
most recent emails (top of the list), viewing each email's content one by
one and returning to the list after each.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ios_agent.connection import IOSConnection
from ios_agent.controller import IOSController
from ios_agent.executor import IOSExecutor
from ios_agent.task import IOSTask
from ios_agent.recorder import IOSRecorder
from utils_mobile.utils import print_with_color


class MailConfig:
    """Config class for Mail pipeline."""

    def __init__(self, task_dir=None, screenshot_dir=None):
        # Get Android-Lab root directory (parent of ios_agent)
        android_lab_root = Path(__file__).parent.parent.parent.parent
        default_log_dir = android_lab_root / "ios_logs"
        self.task_dir = task_dir or str(default_log_dir)
        self.screenshot_dir = screenshot_dir or os.path.join(self.task_dir, "screenshots")


def _set_single_step_instruction(task_agent: IOSTask, instruction: str, opened_count: int = 0):
    """
    Update the task's instruction for *this* round only.

    Important:
    - DO NOT call task_agent.set_system_prompt() here, because it clears record.history.
    - We only rewrite the current instruction + system prompt content.
    """
    progress_info = f"Progress: You have already opened {opened_count} email(s). " if opened_count > 0 else ""
    wrapped = (
        "Overall goal: In Mail app inbox/list, identify the five most recent emails "
        "at the top of the list and open them ONE BY ONE (open -> view content -> go back -> continue) "
        "until five have been opened.\n"
        f"{progress_info}"
        "IMPORTANT: Do NOT open the same email twice. Each email should only be opened once. "
        "If you are currently viewing an email's content, you must go back to the list before opening the next one.\n"
        "Rules: Only perform the [Single step goal] for THIS round. Execute exactly ONE action per round. "
        "Do NOT use any search bar; rely on the visible mail list order. "
        "Do NOT call finish() unless explicitly instructed with 'YOU MAY FINISH NOW'.\n"
        f"Single step goal: {instruction}"
    )

    task_agent.instruction = wrapped
    # Keep system prompt stable except the Task Instruction part.
    if task_agent.system_prompt and isinstance(task_agent.system_prompt, list):
        task_agent.system_prompt[0]["content"] = (
            task_agent.system_prompt[0]["content"].split("\n\nTask Instruction:")[0]
            + f"\n\nTask Instruction: {wrapped}"
        )


def create_mail_pipeline_overview() -> str:
    """Human-readable overview for logs."""
    return (
        "Open Mail app, go to the inbox/mail list, then sequentially open the five most recent "
        "emails (top rows). Enter an email, view its content, return to the list, and continue "
        "until five emails have been opened."
    )


def build_step_instructions():
    """
    Build micro-step instructions for weak local models.

    Each string should be a *single* step. The model will still choose ONE action per round.
    """
    return {
        "open_mail": (
            "Find the Mail app icon on the current screen. "
            "The Mail icon is typically blue in color (light blue or sky blue background) with a white envelope symbol. "
            "It may show the text 'Mail' or '邮件' below it. Look for a square app icon with a distinctive blue color scheme and envelope shape. "
            "Tap it to open the Mail app."
        ),
        "go_inbox": (
            "Inside Mail app, navigate to the main inbox or mail list (usually the default view when opening Mail). "
            "If you see a list of emails, you are already in the inbox. If you are already on the mail list, do nothing extra."
        ),
        "scan_top_five": (
            "On the mail list/inbox, visually identify the top rows. Count the most recent emails from the top "
            "and memorize the first five unique emails. Do NOT tap any email in this step."
        ),
        "enter_next_email": (
            "Tap ONE email among the top five recent emails that you have NOT opened yet in this task. "
            "IMPORTANT: Choose a DIFFERENT email from the ones you have already opened. "
            "Look at the email list and select a NEW email that you have not clicked before. "
            "After opening, stay inside the email content view for this step; do NOT go back in the same round."
        ),
        "back_to_list": (
            "If inside an email's content view, tap the back button to return to the Mail inbox/list so you can open the next email. "
            "If already on the mail list, do nothing."
        ),
        "finish": (
            "YOU MAY FINISH NOW. Report how many recent emails you opened (target: 5). Then call finish()."
        ),
    }


def _get_active_bundle_id(wda_url: str) -> Optional[str]:
    """Best-effort read of active app bundleId from WDA."""
    try:
        import requests

        resp = requests.get(f"{wda_url.rstrip('/')}/wda/activeAppInfo", timeout=5, verify=False)
        if resp.status_code != 200:
            return None
        data = resp.json() if hasattr(resp, "json") else None
        if not isinstance(data, dict):
            return None
        value = data.get("value", {})
        if not isinstance(value, dict):
            return None
        bundle_id = value.get("bundleId")
        return bundle_id if isinstance(bundle_id, str) and bundle_id else None
    except Exception:
        return None


def _is_mail_bundle(bundle_id: Optional[str]) -> bool:
    """Check whether the active bundle belongs to Mail."""
    if not bundle_id:
        return False
    bid = bundle_id.lower()
    return "mail" in bid or bid.startswith("com.apple.mobilemail")


def main():
    parser = argparse.ArgumentParser(
        description="Mail Pipeline for iOS Agent - Open five most recent emails",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--wda-url",
        type=str,
        default=os.getenv("WDA_URL", "http://localhost:8100"),
        help="WebDriverAgent URL",
    )

    parser.add_argument(
        "--max-rounds",
        type=int,
        default=80,
        help="Maximum number of rounds (default: 80).",
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

    parser.add_argument(
        "--step-mode",
        action="store_true",
        default=True,
        help="Use micro-step instructions (recommended for weak local models). Default: True",
    )

    parser.add_argument(
        "--open-mail-timeout",
        type=int,
        default=10,
        help="If stuck opening Mail for too many rounds, force moving on (default: 10).",
    )

    parser.add_argument(
        "--go-inbox-timeout",
        type=int,
        default=6,
        help="If stuck entering inbox/list for too many rounds, force moving on (default: 6).",
    )

    parser.add_argument(
        "--ignore-premature-finish",
        action="store_true",
        default=True,
        help="Ignore finish() calls before the pipeline explicitly allows finishing. Default: True",
    )

    parser.add_argument(
        "--max-no-progress-rounds",
        type=int,
        default=15,
        help="If we cannot open new emails for this many rounds, allow finishing (default: 15).",
    )

    parser.add_argument(
        "--target-email-count",
        type=int,
        default=5,
        help="Number of recent emails to open (default: 5).",
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

    # Create task ID
    task_id = f"mail_task_{int(time.time())}"
    demo_timestamp = int(time.time())
    task_name = task_id + "_" + datetime.fromtimestamp(demo_timestamp).strftime("%Y-%m-%d_%H-%M-%S")

    # Get Android-Lab root directory for default log path
    android_lab_root = Path(__file__).parent.parent.parent.parent
    default_log_base = android_lab_root / "ios_logs"
    
    # Setup config
    config = MailConfig(
        task_dir=args.task_dir or str(default_log_base / task_name),
        screenshot_dir=os.path.join(args.task_dir or str(default_log_base / task_name), "screenshots"),
    )
    os.makedirs(config.task_dir, exist_ok=True)
    os.makedirs(config.screenshot_dir, exist_ok=True)

    # Initialize controller
    controller = IOSController(wda_url=args.wda_url, session_id=session_id)
    controller.screenshot_dir = config.screenshot_dir

    # Initialize executor
    executor = IOSExecutor(wda_url=args.wda_url, session_id=session_id)
    executor.screenshot_dir = config.screenshot_dir

    # Initialize agent
    from agent.model import QwenVLAgent, OpenAIAgent

    agent_type = os.getenv("AGENT_TYPE", "OpenAIAgent").strip()
    api_key = os.getenv("API_KEY", "EMPTY")
    api_base = os.getenv("API_BASE", "http://localhost:8002/v1")
    model_name = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-3B-Instruct")

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
        sys.exit(1)

    if agent_type == "QwenVLAgent":
        agent = QwenVLAgent(
            api_key=api_key,
            api_base=api_base,
            model_name=model_name,
        )
    else:
        agent = OpenAIAgent(
            api_key=api_key,
            api_base=api_base,
            model_name=model_name,
        )

    # Initialize recorder
    record = IOSRecorder(
        id=task_name,
        instruction=create_mail_pipeline_overview(),
        page_executor=executor,
        config=config,
    )

    # Initialize task
    task_agent = IOSTask(
        instruction=create_mail_pipeline_overview(),
        controller=controller,
        page_executor=executor,
        agent=agent,
        record=record,
        command_per_step=None,
    )

    print_with_color("\n📱 Mail Pipeline Task", "green")
    print_with_color(f"Task: {create_mail_pipeline_overview()}\n", "cyan")
    print("=" * 50)

    round_count = 0
    task_complete = False

    steps = build_step_instructions()
    phase = "open_mail"
    phase_rounds = 0
    allow_finish = False
    opened_emails = 0
    no_progress_rounds = 0
    last_was_in_email_view = False  # Track if we were in email view in last round
    consecutive_email_views = 0  # Count consecutive rounds in email view (to detect stuck)

    while round_count < args.max_rounds:
        try:
            round_count += 1
            print_with_color(f"Round {round_count}", "yellow")

            current_app = executor.get_current_app()
            active_bundle_id = _get_active_bundle_id(args.wda_url)

            if args.step_mode:
                if phase == "open_mail":
                    phase_rounds += 1
                    inst_key = "open_mail"
                    if current_app == "Mail" or _is_mail_bundle(active_bundle_id):
                        phase = "go_inbox"
                        phase_rounds = 0
                        inst_key = "go_inbox"
                    elif phase_rounds >= max(1, int(args.open_mail_timeout)):
                        phase = "go_inbox"
                        phase_rounds = 0
                        inst_key = "go_inbox"

                elif phase == "go_inbox":
                    phase_rounds += 1
                    inst_key = "go_inbox"
                    phase = "scan_top_five"
                    phase_rounds = 0

                elif phase == "scan_top_five":
                    inst_key = "scan_top_five"
                    phase = "loop"
                    phase_rounds = 0
                    loop_cycle = ["enter_next_email", "back_to_list"]
                    loop_idx = 0

                else:
                    # loop phase
                    inst_key = loop_cycle[phase_rounds % len(loop_cycle)]
                    phase_rounds += 1
                    
                    # If we're trying to enter email but we're already in email view, force back to list
                    if inst_key == "enter_next_email" and last_was_in_email_view:
                        print_with_color("⚠️  Already in email view, forcing back to list first", "yellow")
                        inst_key = "back_to_list"
                        phase_rounds = 0  # Reset to start cycle again

                _set_single_step_instruction(task_agent, steps[inst_key], opened_emails)
                print_with_color(f"Step instruction: {steps[inst_key]}", "cyan")

            task_agent.run_step(round_count - 1)
            print_with_color("Thinking about what to do in the next step...", "yellow")
            time.sleep(args.request_interval)

            # Detect if we're in email detail view (not in inbox list)
            # This is a heuristic: if we're in Mail app and just executed enter_next_email, we're likely in email view
            is_in_email_view = False
            try:
                # Check if we're in Mail app
                if current_app == "Mail" or _is_mail_bundle(active_bundle_id):
                    # After executing enter_next_email action, we should be in email view
                    if inst_key == "enter_next_email":
                        # After trying to enter email, assume we're in email view
                        is_in_email_view = True
                    elif inst_key == "back_to_list":
                        # After going back, assume we're back in list
                        is_in_email_view = False
                    else:
                        # Keep previous state (for other actions like scan_top_five)
                        is_in_email_view = last_was_in_email_view
            except Exception:
                is_in_email_view = False
            
            # Track consecutive rounds in email view to detect if stuck
            if is_in_email_view:
                consecutive_email_views += 1
            else:
                consecutive_email_views = 0
            
            # If stuck in email view for too long, force back to list next round
            if consecutive_email_views >= 3:
                print_with_color("⚠️  Detected stuck in email view for 3+ rounds, will force back to list", "yellow")
                # Will be handled in next round's phase logic
            
            last_was_in_email_view = is_in_email_view

            # Heuristic progress tracking: if Tap issued while trying to enter email, count it.
            try:
                last = task_agent.record.contents[-1] if task_agent.record.contents else {}
                exe_res = last.get("execution_result") if isinstance(last, dict) else None
                last_action = (exe_res or {}).get("action") if isinstance(exe_res, dict) else None
            except Exception:
                last_action = None

            # Only count as opened if we successfully entered email view AND we weren't already in email view
            if args.step_mode and inst_key == "enter_next_email" and last_action == "Tap" and not last_was_in_email_view:
                opened_emails += 1
                no_progress_rounds = 0
                print_with_color(f"Opened email count: {opened_emails}/{args.target_email_count}", "green")
            elif args.step_mode and inst_key == "enter_next_email" and last_was_in_email_view:
                # Tried to open email but we're already in email view - might be repeating
                print_with_color("⚠️  Warning: Attempted to open email while already in email view (possible repeat)", "yellow")
                no_progress_rounds += 1
            elif args.step_mode and inst_key in ("enter_next_email",):
                no_progress_rounds += 1

            if opened_emails >= args.target_email_count:
                allow_finish = True

            if no_progress_rounds >= max(1, int(args.max_no_progress_rounds)):
                allow_finish = True

            # Guard: model may call finish() too early.
            if task_agent.page_executor.is_finish and args.ignore_premature_finish and not allow_finish:
                print_with_color(
                    "⚠️  Model called finish() early; ignoring to continue the pipeline.",
                    "red",
                )
                task_agent.page_executor.is_finish = False

            if allow_finish and not task_agent.page_executor.is_finish and args.step_mode:
                _set_single_step_instruction(
                    task_agent,
                    steps["finish"].replace("5", str(args.target_email_count)),
                )

            if task_agent.page_executor.is_finish:
                print_with_color("Completed successfully.", "green")
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
        print_with_color("✅ Mail pipeline completed!", "green")
    else:
        print_with_color("❌ Mail pipeline incomplete or failed", "red")
        print_with_color(f"Completed {round_count} rounds out of {args.max_rounds}", "yellow")


if __name__ == "__main__":
    main()
