"""iOS Recorder - adapts iOS device recording to Android-Lab's recorder interface."""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Add parent directory to path to import Android-Lab modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from ios_agent.screenshot import Screenshot
from ios_agent.hierarchy import get_page_source, get_ios_elements
from ios_agent.labeling import draw_bbox_multi_ios


class IOSRecorder:
    """
    iOS Recorder that adapts iOS device recording to Android-Lab's recorder interface.
    
    This class provides methods compatible with Android-Lab's JSONRecorder,
    adapted for iOS devices (no XML, only screenshots).
    """

    def __init__(self, id: str, instruction: str, page_executor, config=None):
        """
        Initialize iOS recorder.
        
        Args:
            id: Task ID.
            instruction: Task instruction.
            page_executor: IOSExecutor instance.
            config: Optional config object with task_dir, screenshot_dir, etc.
        """
        self.id = id
        self.instruction = instruction
        self.page_executor = page_executor
        
        self.turn_number = 0
        
        # Setup directories
        if config and hasattr(config, 'task_dir'):
            task_dir = config.task_dir
        else:
            task_dir = f"./ios_logs/{id}"
        
        trace_dir = os.path.join(task_dir, 'traces')
        screenshot_dir = os.path.join(task_dir, 'screenshots')
        xml_dir = os.path.join(task_dir, 'xml')
        log_dir = task_dir
        
        os.makedirs(trace_dir, exist_ok=True)
        os.makedirs(screenshot_dir, exist_ok=True)
        os.makedirs(xml_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)
        
        self.trace_file_path = os.path.join(trace_dir, 'trace.jsonl')
        self.screenshot_dir = screenshot_dir
        self.xml_dir = xml_dir
        self.log_dir = log_dir
        
        self.contents = []
        self.history = []
        self.current_screenshot_path: Optional[str] = None
        self.labeled_current_screenshot_path: Optional[str] = None
        self.xml_history = []

    def update_before(self, controller, need_screenshot: bool = False, need_labeled: bool = False, **kwargs):
        """
        Update recorder before action execution.
        
        Args:
            controller: IOSController instance.
            need_screenshot: Whether to capture screenshot.
            need_labeled: Whether to generate labeled screenshot.
            **kwargs: Additional arguments (ignored, kept for compatibility).
        """
        xml_path = None
        xml_string = None
        
        # Step 1: Try to get page source (XML) via controller
        # print(f"[Turn {self.turn_number}] Getting page source (XML)...")  # Commented out XML logs
        xml_status = controller.get_xml(prefix=str(self.turn_number), save_dir=self.xml_dir)
        if "ERROR" not in xml_status and xml_status == "SUCCESS":
            xml_path = os.path.join(self.xml_dir, f"{self.turn_number}.xml")
            self.xml_history.append(xml_path)
            # print(f"✓ XML saved to: {xml_path}")  # Commented out XML logs
        
        # Step 2: Capture screenshot if needed
        if need_screenshot:
            # print(f"[Turn {self.turn_number}] Capturing screenshot...")  # Commented out screenshot logs
            self.page_executor.update_screenshot(prefix=str(self.turn_number), suffix="before")
            self.current_screenshot_path = self.page_executor.current_screenshot_path
            # if self.current_screenshot_path:
            #     print(f"✓ Screenshot saved to: {self.current_screenshot_path}")  # Commented out screenshot logs
        
        # Step 3: Get XML string and parse elements (needed for tap_by_index, etc.)
        # This should happen even if labeled screenshot is not needed
        # print(f"[Turn {self.turn_number}] Parsing XML and extracting elements...")  # Commented out XML logs
        try:
            # First, try to read from saved XML file
            if xml_path and os.path.exists(xml_path):
                try:
                    with open(xml_path, 'r', encoding='utf-8') as f:
                        xml_string = f.read()
                    if xml_string and len(xml_string.strip()) > 0:
                        # print(f"✓ Loaded XML from file: {xml_path} ({len(xml_string)} chars)")  # Commented out XML logs
                        pass
                    else:
                        # print(f"⚠️  Warning: XML file {xml_path} is empty")  # Commented out XML logs
                        xml_string = None
                except Exception as e:
                    # print(f"⚠️  Warning: Failed to read XML file {xml_path}: {e}")  # Commented out XML logs
                    xml_string = None
            
            # Fallback: get page source directly if XML file doesn't exist or failed to read
            if not xml_string:
                # print("  Attempting to get page source directly from WebDriverAgent...")  # Commented out XML logs
                try:
                    xml_string = get_page_source(
                        wda_url=controller.wda_url,
                        session_id=controller.session_id,
                        timeout=15  # Use longer timeout for direct fetch
                    )
                    if xml_string and len(xml_string.strip()) > 0:
                        # print(f"✓ Got page source directly ({len(xml_string)} chars)")  # Commented out XML logs
                        # Save it for future reference
                        if xml_path:
                            try:
                                os.makedirs(os.path.dirname(xml_path), exist_ok=True)
                                with open(xml_path, 'w', encoding='utf-8') as f:
                                    f.write(xml_string)
                                # print(f"✓ Saved XML to: {xml_path}")  # Commented out XML logs
                            except Exception as e:
                                # print(f"⚠️  Warning: Failed to save XML: {e}")  # Commented out XML logs
                                pass
                    # else:
                    #     print("⚠️  Warning: get_page_source returned None or empty, element list will be empty")  # Commented out XML logs
                except Exception as e:
                    # print(f"⚠️  Warning: Failed to get page source: {e}")  # Commented out XML logs
                    # import traceback
                    # traceback.print_exc()
                    pass
            
            # Parse XML and set element list
            if xml_string and len(xml_string.strip()) > 0:
                # print(f"  Parsing XML and extracting interactive elements...")  # Commented out XML logs
                try:
                    self.page_executor.set_elem_list(xml_string)
                    elem_count = len(self.page_executor.elem_list)
                    # if elem_count > 0:
                    #     print(f"✓ Successfully parsed {elem_count} interactive elements")  # Commented out XML logs
                    # else:
                    #     print(f"⚠️  Warning: XML parsed but found 0 interactive elements")  # Commented out XML logs
                    #     # Debug: print first 500 chars of XML to see what we got
                    #     preview = xml_string[:500].replace('\n', '\\n')
                    #     print(f"  XML preview: {preview}...")  # Commented out XML logs
                except Exception as e:
                    # print(f"⚠️  Error parsing XML: {e}")  # Commented out XML logs
                    # import traceback
                    # traceback.print_exc()
                    self.page_executor.elem_list = []
            else:
                # If XML is not available, clear elem_list and warn
                self.page_executor.elem_list = []
                # print("⚠️  Warning: Could not get XML/page source, element list will be empty")  # Commented out XML logs
                # print("  This means tap_by_index() and other index-based actions will not work.")  # Commented out XML logs
                # print("  Coordinate-based actions (tap(x, y)) will still work.")  # Commented out XML logs
                pass
                
        except Exception as e:
            print(f"⚠️  Error setting element list: {e}")
            import traceback
            traceback.print_exc()
            self.page_executor.elem_list = []
        
        # Step 4: Generate labeled screenshot if needed
        if need_labeled and self.current_screenshot_path:
            # print(f"[Turn {self.turn_number}] Generating labeled screenshot...")  # Commented out screenshot logs
            try:
                # Check if we have elements to label
                if not self.page_executor.elem_list or len(self.page_executor.elem_list) == 0:
                    # print("⚠️  Warning: Element list is empty, cannot generate labeled screenshot")  # Commented out logs
                    # print("  Falling back to regular screenshot")  # Commented out logs
                    self.labeled_current_screenshot_path = self.current_screenshot_path
                else:
                    labeled_path = self.current_screenshot_path.replace(".png", "_labeled.png")
                    
                    # Calculate scale factor from screenshot dimensions
                    import cv2
                    img = cv2.imread(self.current_screenshot_path)
                    if img is not None:
                        height, width = img.shape[:2]
                        # Estimate scale factor (iOS screenshots are typically 3x logical size)
                        # Common logical sizes: 375x812, 390x844, 393x852
                        scale_factor = None
                        if width >= 1100:  # Physical coordinate
                            # Try to match with common logical widths
                            for logical_width in [375, 390, 393]:
                                if abs(width / logical_width - 3.0) < 0.1:
                                    scale_factor = width / logical_width
                                    break
                            if scale_factor is None:
                                scale_factor = width / 375.0  # Default estimate
                        else:
                            scale_factor = 1.0  # Already logical coordinates
                        
                        # print(f"  Using scale factor: {scale_factor:.2f} (screenshot: {width}x{height})")  # Commented out logs
                    else:
                        scale_factor = None  # Will use auto-detection
                        # print("  Warning: Could not read screenshot for scale factor detection, using auto-detection")  # Commented out logs
                    
                    # Draw bounding boxes on screenshot
                    # print(f"  Drawing {len(self.page_executor.elem_list)} bounding boxes...")  # Commented out logs
                    result = draw_bbox_multi_ios(
                        self.current_screenshot_path,
                        labeled_path,
                        self.page_executor.elem_list,
                        record_mode=False,
                        dark_mode=False,
                        scale_factor=scale_factor
                    )
                    
                    if result is not None:
                        self.labeled_current_screenshot_path = labeled_path
                        # print(f"✓ Labeled screenshot saved to: {labeled_path}")  # Commented out logs
                    else:
                        # print("⚠️  Warning: Failed to generate labeled screenshot, using regular screenshot")  # Commented out logs
                        self.labeled_current_screenshot_path = self.current_screenshot_path
                        
            except Exception as e:
                # import traceback
                # print(f"❌ Error generating labeled screenshot: {e}")  # Commented out logs
                # print(traceback.format_exc())
                # print("  Falling back to regular screenshot")  # Commented out logs
                self.labeled_current_screenshot_path = self.current_screenshot_path
        elif need_labeled:
            # Screenshot not available, can't generate labeled version
            # print("⚠️  Warning: Screenshot not available, cannot generate labeled screenshot")  # Commented out logs
            self.labeled_current_screenshot_path = None
        
        # Create step record
        step = {
            "trace_id": self.id,
            "index": self.turn_number,
            "prompt": "** screenshot **" if self.turn_number > 0 else f"{self.instruction}",
            "image": self.current_screenshot_path,
            "labeled_image": self.labeled_current_screenshot_path if need_labeled else None,
            "xml": xml_path,
            "current_app": controller.get_current_app(),
            "window": controller.viewport_size,
            "target": self.instruction,
        }
        
        self.contents.append(step)

    def update_after(self, exe_res, response: str):
        """
        Update recorder after action execution.
        
        Args:
            exe_res: Execution result from executor.
            response: Agent response.
        """
        if self.contents:
            self.contents[-1]["response"] = response
            self.contents[-1]["execution_result"] = exe_res
        
        # Add to history
        self.history.append({
            "role": "assistant",
            "content": response
        })

    def update_after_cot(self, exe_res, response: str, prompt_his: Optional[str] = None,
                        code_snippet: Optional[str] = None, cloud_status: bool = False,
                        control_status: bool = False):
        """
        Update recorder after action execution (CoT version).
        
        Args:
            exe_res: Execution result from executor.
            response: Agent response.
            prompt_his: Prompt history from state assessment.
            code_snippet: Code snippet extracted from response.
            cloud_status: Whether cloud agent was used (always False for iOS).
            control_status: Whether control agent was used (always False for iOS).
        """
        if self.contents:
            self.contents[-1]["response"] = response
            self.contents[-1]["execution_result"] = exe_res
            if prompt_his:
                self.contents[-1]["prompt_his"] = prompt_his
            if code_snippet:
                self.contents[-1]["code_snippet"] = code_snippet
            self.contents[-1]["cloud_status"] = cloud_status
            self.contents[-1]["control_status"] = control_status
        
        # Add to history: only store compact prompt_his (state assessment) to keep prompts small,
        # matching Android local_agent behavior.
        if prompt_his:
            self.history.append(prompt_his)
        
        # Save trace
        self._save_trace()

    def get_latest_xml(self) -> str:
        """
        Get latest XML string from page source.
        
        Compatible with Android-Lab's get_latest_xml interface.
        
        Returns:
            XML string or empty string if not available.
        """
        if self.xml_history:
            latest_xml_path = self.xml_history[-1]
            if os.path.exists(latest_xml_path):
                try:
                    with open(latest_xml_path, 'r', encoding='utf-8') as f:
                        return f.read()
                except Exception as e:
                    print(f"Error reading XML: {e}")
        
        return ""

    def _save_trace(self):
        """Save trace to JSONL file."""
        if self.contents:
            with open(self.trace_file_path, 'a', encoding='utf-8') as f:
                json.dump(self.contents[-1], f, ensure_ascii=False)
                f.write('\n')
