"""iOS Task - adapts iOS device automation to Android-Lab's task framework."""

import re
import sys
import time
from pathlib import Path
from typing import Optional

# Add parent directory to path to import Android-Lab modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from ios_agent.prompts import SYSTEM_PROMPT_IOS_MLLM_DIRECT
from evaluation.definition import get_code_snippet_cot_v3


class IOSTask:
    """
    iOS Task that adapts iOS device automation to Android-Lab's task framework.
    
    This class is simplified to only use local_agent, following the pattern
    from evaluation.py's ScreenshotTask.run_step method.
    """

    def __init__(self, instruction: str, controller, page_executor, agent, record, **kwargs):
        """
        Initialize iOS task.
        
        Args:
            instruction: Task instruction.
            controller: IOSController instance.
            page_executor: IOSExecutor instance.
            agent: Agent instance (from agent.model).
            record: Recorder instance.
            **kwargs: Additional arguments.
        """
        self.controller = controller
        self.page_executor = page_executor
        self.agent = agent
        self.record = record
        self.instruction = instruction
        self.kwargs = kwargs
        self.set_system_prompt(instruction)

    def set_system_prompt(self, instruction: str):
        """Set system prompt for the agent."""
        # For iOS we follow the Android local_agent pattern:
        # - Keep system prompt separately (as messages passed to the model)
        # - Keep record.history as a list of compact prompt_his strings from previous turns
        self.record.history = []  # history will store only prompt_his strings
        self.system_prompt = [{
            "role": "system",
            "content": SYSTEM_PROMPT_IOS_MLLM_DIRECT + f"\n\nTask Instruction: {instruction}"
        }]

    def run_step(self, round_count: int):
        """
        Execute a single step of the task.
        
        This method follows the pattern from ScreenshotTask.run_step,
        simplified to only use local_agent.
        
        Args:
            round_count: Current round number (0-indexed).
        """
        # Update before: capture screenshot and generate labeled screenshot
        self.record.update_before(
            controller=self.controller,
            need_screenshot=True,
            need_labeled=True  # Enable labeled screenshot generation
        )
        
        try:
            # Get labeled screenshot path (preferred) or regular screenshot path
            image_path = self.record.labeled_current_screenshot_path or self.record.current_screenshot_path
            
            def build_prompt(prefix=""):
                """Build prompt with instruction and a compact history string."""
                # Only keep the most recent few state assessments to avoid oversized prompts
                history_tail = self.record.history[-4:] if self.record.history else []
                history_text = "\n".join(history_tail) if history_tail else "[]"
                base = f"{self.instruction}\nHistory Information:\n{history_text}\nCurrent Information: <image>"
                return (prefix + base) if prefix else base

            def use_local_agent(prompt_text):
                """Use local agent to get response."""
                current_message = self.agent.prompt_to_message_visual(prompt_text, image_path)
                # Combine system prompt and current user message
                return self.agent.act([*self.system_prompt, *current_message])

            # Execute with local agent
            rsp = use_local_agent(build_prompt())

            # Extract code snippet from response
            code_snippet = get_code_snippet_cot_v3(rsp)
            
            # Execute the action (skip if code_snippet is None)
            if code_snippet:
                exe_res = self.page_executor(code_snippet)
            else:
                print("Warning: Could not extract code snippet from response, skipping action")
                exe_res = {
                    "operation": "skip",
                    "action": "skip",
                    "kwargs": {"reason": "Failed to extract code snippet"}
                }
            
            # Extract state assessment if present
            pattern = r'<STATE_ASSESSMENT>\s*(.*?)\s*</STATE_ASSESSMENT>'
            match = re.search(pattern, rsp, re.DOTALL)
            prompt_his = match.group(1) if match else None

        except Exception as e:
            import traceback
            print(traceback.print_exc())
            exe_res = None
            rsp = f"Error: {e}"
            prompt_his = None
            code_snippet = None
        
        # Update record
        self.record.update_after_cot(exe_res, rsp, prompt_his, code_snippet, cloud_status=False)
        self.record.turn_number += 1
