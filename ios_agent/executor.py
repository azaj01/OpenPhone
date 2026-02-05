"""iOS executor for Android-Lab - adapts iOS actions to Android-Lab interface."""

import time
from typing import Optional, List

from ios_agent.actions import IOSActionHandler
from ios_agent.screenshot import get_screenshot, Screenshot
from ios_agent.hierarchy import IOSElement, get_page_source, get_ios_elements


class IOSExecutor:
    """
    iOS executor that adapts iOS device control to Android-Lab's executor interface.
    
    This class provides methods compatible with Android-Lab's executor pattern,
    allowing iOS devices to be used with the same agent code.
    """

    def __init__(self, wda_url: str = "http://localhost:8100", session_id: Optional[str] = None):
        """
        Initialize iOS executor.
        
        Args:
            wda_url: WebDriverAgent URL.
            session_id: Optional WDA session ID.
        """
        self.action_handler = IOSActionHandler(wda_url=wda_url, session_id=session_id)
        self.wda_url = wda_url
        self.session_id = session_id
        self.current_screenshot: Optional[Screenshot] = None
        self.current_return = None
        self.is_finish = False
        self.elem_list: List[IOSElement] = []  # For labeled screenshot support
        self.current_screenshot_path: Optional[str] = None  # Path to current screenshot file

    def get_screenshot(self) -> Screenshot:
        """Get current screenshot."""
        self.current_screenshot = get_screenshot(
            wda_url=self.wda_url,
            session_id=self.session_id,
        )
        return self.current_screenshot

    def tap(self, x: int, y: int) -> dict:
        """
        Tap at coordinates (x, y).
        
        Compatible with Android-Lab's tap interface.
        """
        success = self.action_handler.tap(x, y)
        self.current_return = {
            "operation": "do",
            "action": "Tap",
            "kwargs": {"element": [x, y]}
        }
        return self.current_return

    def text(self, input_str: str) -> dict:
        """
        Type text into the currently focused input field.
        
        Compatible with Android-Lab's text interface.
        """
        # Clear existing text first
        self.action_handler.clear_text()
        time.sleep(0.5)
        
        # Type new text
        success = self.action_handler.type_text(input_str)
        time.sleep(0.5)
        
        # Hide keyboard
        self.action_handler.hide_keyboard()
        time.sleep(0.5)
        
        self.current_return = {
            "operation": "do",
            "action": "Type",
            "kwargs": {"text": input_str}
        }
        return self.current_return

    def type(self, input_str: str) -> dict:
        """Alias for text method."""
        return self.text(input_str)

    def long_press(self, x: int, y: int) -> dict:
        """
        Long press at coordinates (x, y).
        
        Compatible with Android-Lab's long_press interface.
        """
        success = self.action_handler.long_press(x, y)
        self.current_return = {
            "operation": "do",
            "action": "Long Press",
            "kwargs": {"element": [x, y]}
        }
        return self.current_return

    def swipe(self, x: int, y: int, direction: str, dist: str = "medium") -> dict:
        """
        Swipe from coordinates (x, y) in the specified direction.
        
        Args:
            x: Starting X coordinate (assumed to be physical/screenshot coordinates).
            y: Starting Y coordinate (assumed to be physical/screenshot coordinates).
            direction: Direction to swipe ("up", "down", "left", "right").
            dist: Distance of swipe ("short", "medium", "long").
        
        Compatible with Android-Lab's swipe interface.
        
        Note:
            Input coordinates are assumed to be physical coordinates (from screenshots).
            They will be converted to logical coordinates before sending to WDA.
            Screen size calculations use logical coordinates for consistency.
        """
        # Get screen size (logical coordinates from WDA)
        screen_width_logical, screen_height_logical = self.action_handler.get_screen_size()
        
        # Convert input coordinates from physical to logical
        # This ensures consistency with screen_size which is in logical coordinates
        from ios_agent.actions import _physical_to_logical
        x_logical, y_logical = _physical_to_logical(x, y)
        
        # Calculate swipe distance based on dist parameter (using logical coordinates)
        dist_multiplier = {"short": 0.3, "medium": 0.5, "long": 0.7}.get(dist, 0.5)
        
        # Calculate end coordinates based on direction (in logical coordinates)
        if direction == "up":
            end_x_logical = x_logical
            end_y_logical = max(0, int(y_logical - screen_height_logical * dist_multiplier))
        elif direction == "down":
            end_x_logical = x_logical
            end_y_logical = min(screen_height_logical, int(y_logical + screen_height_logical * dist_multiplier))
        elif direction == "left":
            end_x_logical = max(0, int(x_logical - screen_width_logical * dist_multiplier))
            end_y_logical = y_logical
        elif direction == "right":
            end_x_logical = min(screen_width_logical, int(x_logical + screen_width_logical * dist_multiplier))
            end_y_logical = y_logical
        else:
            # Default to down if invalid direction
            end_x_logical = x_logical
            end_y_logical = min(screen_height_logical, int(y_logical + screen_height_logical * dist_multiplier))

        # Convert end coordinates back to physical for consistency with action_handler interface
        # Note: action_handler.swipe expects physical coordinates and will convert internally
        from ios_agent.actions import _logical_to_physical
        end_x, end_y = _logical_to_physical(end_x_logical, end_y_logical)

        success = self.action_handler.swipe(x, y, end_x, end_y)
        self.current_return = {
            "operation": "do",
            "action": "Swipe",
            "kwargs": {
                "element": [x, y],
                "direction": direction,
                "dist": dist
            }
        }
        return self.current_return

    def back(self) -> dict:
        """
        Navigate back (swipe from left edge on iOS).
        
        Compatible with Android-Lab's back interface.
        """
        success = self.action_handler.back()
        self.current_return = {
            "operation": "do",
            "action": "Back",
            "kwargs": {}
        }
        return self.current_return

    def home(self) -> dict:
        """
        Press the home button.
        
        Compatible with Android-Lab's home interface.
        """
        success = self.action_handler.home()
        self.current_return = {
            "operation": "do",
            "action": "Home",
            "kwargs": {}
        }
        return self.current_return

    def wait(self, interval: int = 5) -> dict:
        """
        Wait for specified interval.
        
        Compatible with Android-Lab's wait interface.
        """
        if interval < 0 or interval > 10:
            interval = 5
        time.sleep(interval)
        self.current_return = {
            "operation": "do",
            "action": "Wait",
            "kwargs": {"interval": interval}
        }
        return self.current_return

    def enter(self) -> dict:
        """
        Press Enter key.
        
        Note: iOS doesn't have a universal Enter key, this is a placeholder.
        """
        # On iOS, we can't directly press Enter, but we can hide keyboard
        # which often submits forms
        self.action_handler.hide_keyboard()
        self.current_return = {
            "operation": "do",
            "action": "Enter",
            "kwargs": {}
        }
        return self.current_return

    def launch(self, app_name: str) -> dict:
        """
        Launch an app by name.
        
        Compatible with Android-Lab's launch interface.
        """
        success = self.action_handler.launch_app(app_name)
        self.current_return = {
            "operation": "do",
            "action": "Launch",
            "kwargs": {"app_name": app_name}
        }
        return self.current_return

    def finish(self, message: Optional[str] = None) -> dict:
        """
        Finish the task.
        
        Compatible with Android-Lab's finish interface.
        """
        self.is_finish = True
        self.current_return = {
            "operation": "finish",
            "action": "finish",
            "kwargs": {"message": message}
        }
        return self.current_return

    def get_current_app(self) -> str:
        """Get the currently active app name."""
        return self.action_handler.get_current_app()

    def get_screen_size(self) -> tuple[int, int]:
        """Get the screen dimensions."""
        return self.action_handler.get_screen_size()

    def set_elem_list(self, xml_path_or_string: str):
        """
        Set element list from iOS XML source.
        
        Compatible with Android-Lab's set_elem_list interface.
        
        Args:
            xml_path_or_string: Path to XML file or XML string from page source.
        """
        # If it's a file path, read it
        import os
        if os.path.exists(xml_path_or_string):
            with open(xml_path_or_string, 'r', encoding='utf-8') as f:
                xml_string = f.read()
        else:
            # Assume it's XML string
            xml_string = xml_path_or_string
        
        # Parse and extract elements
        self.elem_list = get_ios_elements(xml_string)

    def tap_by_index(self, index: int) -> dict:
        """
        Tap element by index (for labeled screenshot support).
        
        Compatible with Android-Lab's tap(index) interface.
        
        Args:
            index: Element index (1-based).
        """
        if not self.elem_list:
            error_msg = (
                "Element list is empty. Please ensure XML is parsed and set_elem_list() is called. "
                "This usually means XML parsing failed or no interactive elements were found."
            )
            print(f"Error: {error_msg}")
            self.current_return = {
                "operation": "error",
                "action": "Tap",
                "kwargs": {
                    "index": index,
                    "error": error_msg
                }
            }
            raise ValueError(error_msg)
        assert 0 < index <= len(self.elem_list), f"Tap Index {index} out of range (available: 1-{len(self.elem_list)})"
        
        # Get bbox from elem_list (in logical coordinates)
        tl, br = self.elem_list[index - 1].bbox
        x_logical, y_logical = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        
        # Convert logical coordinates to physical coordinates
        from ios_agent.actions import _logical_to_physical
        x, y = _logical_to_physical(x_logical, y_logical)
        
        return self.tap(x, y)

    def long_press_by_index(self, index: int) -> dict:
        """
        Long press element by index (for labeled screenshot support).
        
        Compatible with Android-Lab's long_press(index) interface.
        
        Args:
            index: Element index (1-based).
        """
        if not self.elem_list:
            raise ValueError("Element list is empty. Please ensure XML is parsed and set_elem_list() is called.")
        assert 0 < index <= len(self.elem_list), f"Long Press Index {index} out of range (available: 1-{len(self.elem_list)})"
        
        # Get bbox from elem_list (in logical coordinates)
        tl, br = self.elem_list[index - 1].bbox
        x_logical, y_logical = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        
        # Convert logical coordinates to physical coordinates
        from ios_agent.actions import _logical_to_physical
        x, y = _logical_to_physical(x_logical, y_logical)
        
        return self.long_press(x, y)

    def swipe_by_index(self, index: int, direction: str, dist: str = "medium") -> dict:
        """
        Swipe element by index (for labeled screenshot support).
        
        Compatible with Android-Lab's swipe(index, direction, dist) interface.
        
        Args:
            index: Element index (1-based).
            direction: Direction to swipe ("up", "down", "left", "right").
            dist: Distance of swipe ("short", "medium", "long").
        """
        if not self.elem_list:
            raise ValueError("Element list is empty. Please ensure XML is parsed and set_elem_list() is called.")
        assert 0 < index <= len(self.elem_list), f"Swipe Index {index} out of range (available: 1-{len(self.elem_list)})"
        
        # Get bbox from elem_list (in logical coordinates)
        tl, br = self.elem_list[index - 1].bbox
        x_logical, y_logical = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        
        # Convert logical coordinates to physical coordinates
        from ios_agent.actions import _logical_to_physical
        x, y = _logical_to_physical(x_logical, y_logical)
        
        return self.swipe(x, y, direction, dist)

    def __call__(self, code_snippet: str):
        """
        Execute code snippet - compatible with Android-Lab's executor interface.
        
        This allows the executor to be called like: executor(code_snippet)
        The code snippet typically contains function calls like tap(5), swipe(10, "up", "medium"), etc.
        
        Args:
            code_snippet: Code string to execute (e.g., "tap(5)" or "swipe(10, 'up', 'medium')").
        """
        import re
        import inspect
        from functools import partial
        
        if not code_snippet:
            print("Warning: code_snippet is empty or None, skipping execution")
            self.current_return = {
                "operation": "skip",
                "action": "skip",
                "kwargs": {"reason": "Empty code snippet"}
            }
            return self.current_return
        
        # Get available methods
        local_context = {}
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if not name.startswith('_'):
                local_context[name] = partial(method, self)
        
        # Add index-based methods for labeled screenshot support
        local_context['tap'] = self.tap_by_index
        local_context['long_press'] = self.long_press_by_index
        local_context['swipe'] = self.swipe_by_index
        local_context['text'] = self.text
        local_context['type'] = self.type
        local_context['back'] = self.back
        local_context['home'] = self.home
        local_context['wait'] = self.wait
        local_context['finish'] = self.finish
        
        # Remove leading zeros in string (Android-Lab compatibility)
        code_snippet = re.sub(r'\b0+(\d)', r'\1', code_snippet)
        
        # Execute code
        try:
            exec(code_snippet, {}, local_context)
        except ValueError as e:
            # Handle empty elem_list error gracefully
            if "Element list is empty" in str(e):
                print(f"Error: {e}")
                print("Attempting to re-fetch XML and element list...")
                # Try to re-fetch XML (this might not work if called from executor context)
                # For now, just set a proper error return
                self.current_return = {
                    "operation": "error",
                    "action": "error",
                    "kwargs": {
                        "error": str(e),
                        "message": "Element list is empty. XML parsing may have failed."
                    }
                }
            else:
                print(f"Error executing code snippet: {e}")
                import traceback
                traceback.print_exc()
                self.current_return = {
                    "operation": "error",
                    "action": "error",
                    "kwargs": {"error": str(e)}
                }
        except Exception as e:
            print(f"Error executing code snippet: {e}")
            import traceback
            traceback.print_exc()
            self.current_return = {
                "operation": "error",
                "action": "error",
                "kwargs": {"error": str(e)}
            }
        
        return self.current_return

    def do(self, action=None, element=None, **kwargs):
        """
        Execute an action - compatible with Android-Lab's do() interface.
        
        Args:
            action: Action name ("Tap", "Type", "Swipe", "Long Press", "Home", "Back", "Enter", "Wait", "Launch", "Call_API")
            element: Element coordinates or area
            **kwargs: Additional arguments for the action
        """
        assert action in [
            "Tap", "Type", "Swipe", "Enter", "Home", "Back", "Long Press", "Wait", "Launch", "Call_API"
        ], f"Unsupported Action: {action}"

        if action == "Tap":
            if isinstance(element, list) and len(element) == 4:
                center_x = (element[0] + element[2]) / 2
                center_y = (element[1] + element[3]) / 2
            elif isinstance(element, list) and len(element) == 2:
                center_x, center_y = element
            else:
                raise ValueError("Invalid element format for Tap")
            return self.tap(int(center_x), int(center_y))

        elif action == "Type":
            assert "text" in kwargs, "text is required for Type action"
            return self.text(kwargs["text"])

        elif action == "Swipe":
            assert "direction" in kwargs, "direction is required for Swipe action"
            if element is None:
                # Get screen size (logical coordinates) and convert to physical
                screen_width_logical, screen_height_logical = self.get_screen_size()
                from ios_agent.actions import _logical_to_physical
                center_x, center_y = _logical_to_physical(
                    screen_width_logical // 2, 
                    screen_height_logical // 2
                )
            elif isinstance(element, list) and len(element) == 4:
                center_x = (element[0] + element[2]) / 2
                center_y = (element[1] + element[3]) / 2
            elif isinstance(element, list) and len(element) == 2:
                center_x, center_y = element
            else:
                raise ValueError("Invalid element format for Swipe")
            dist = kwargs.get("dist", "medium")
            return self.swipe(int(center_x), int(center_y), kwargs["direction"], dist)

        elif action == "Enter":
            return self.enter()

        elif action == "Home":
            return self.home()

        elif action == "Back":
            return self.back()

        elif action == "Long Press":
            if isinstance(element, list) and len(element) == 4:
                center_x = (element[0] + element[2]) / 2
                center_y = (element[1] + element[3]) / 2
            elif isinstance(element, list) and len(element) == 2:
                center_x, center_y = element
            else:
                raise ValueError("Invalid element format for Long Press")
            return self.long_press(int(center_x), int(center_y))

        elif action == "Wait":
            interval = kwargs.get("interval", 5)
            return self.wait(interval)

        elif action == "Launch":
            assert "app" in kwargs or "app_name" in kwargs, "app or app_name is required for Launch action"
            app_name = kwargs.get("app") or kwargs.get("app_name")
            return self.launch(app_name)

        elif action == "Call_API":
            # Call_API is typically used for content summarization or analysis
            # This is a placeholder implementation - actual implementation depends on requirements
            instruction = kwargs.get("instruction", "")
            with_screen_info = kwargs.get("with_screen_info", True)
            self.current_return = {
                "operation": "do",
                "action": "Call_API",
                "kwargs": {
                    "instruction": instruction,
                    "with_screen_info": with_screen_info
                }
            }
            return self.current_return

        else:
            raise NotImplementedError(f"Action {action} not implemented")

    def update_screenshot(self, prefix=None, suffix=None):
        """
        Update screenshot - compatible with Android-Lab's update_screenshot interface.
        
        Note: On iOS, we get screenshots on-demand, so this just updates the current screenshot.
        """
        import os
        import time
        screenshot = self.get_screenshot()
        
        # Save screenshot if screenshot_dir is set
        if hasattr(self, 'screenshot_dir'):
            if prefix is None and suffix is None:
                screenshot_path = f"{self.screenshot_dir}/screenshot-{time.time()}.png"
            elif prefix is not None and suffix is None:
                screenshot_path = f"{self.screenshot_dir}/screenshot-{prefix}-{time.time()}.png"
            elif prefix is None and suffix is not None:
                screenshot_path = f"{self.screenshot_dir}/screenshot-{time.time()}-{suffix}.png"
            else:
                screenshot_path = f"{self.screenshot_dir}/screenshot-{prefix}-{time.time()}-{suffix}.png"
            
            from ios_agent.screenshot import save_screenshot
            save_screenshot(screenshot, screenshot_path)
            self.current_screenshot_path = screenshot_path
            self.current_screenshot = screenshot_path  # For compatibility with Android-Lab
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        
        return screenshot
