"""Action execution for iOS devices via WebDriverAgent."""

import time
from typing import Optional, Tuple

# iOS app bundle IDs - can be extended
APP_PACKAGES_IOS = {
    "Safari": "com.apple.mobilesafari",
    "Settings": "com.apple.Preferences",
    "Messages": "com.apple.MobileSMS",
    "Mail": "com.apple.mobilemail",
    "Photos": "com.apple.mobileslideshow",
    "Camera": "com.apple.camera",
    "Clock": "com.apple.mobiletimer",
    "Calendar": "com.apple.mobilecal",
    "Maps": "com.apple.Maps",
    "Music": "com.apple.Music",
    "App Store": "com.apple.AppStore",
    "Notes": "com.apple.mobilenotes",
    "Reminders": "com.apple.reminders",
    "Weather": "com.apple.weather",
    "Calculator": "com.apple.calculator",
    "Contacts": "com.apple.MobileAddressBook",
    "FaceTime": "com.apple.facetime",
    "Phone": "com.apple.mobilephone",
    "Feishu": "com.bytedance.feishu",
    "Lark": "com.bytedance.lark",
    "WeChat": "com.tencent.xinWeChat",
    "Meituan": "com.sankuai.meituan",
}

SCALE_FACTOR = 3  # 3 for most modern iPhone


def _physical_to_logical(x: int, y: int) -> Tuple[int, int]:
    """
    Convert physical coordinates (screenshot coordinates) to logical coordinates (WDA coordinates).
    
    Args:
        x: Physical X coordinate.
        y: Physical Y coordinate.
    
    Returns:
        Tuple of (logical_x, logical_y).
    """
    return int(x / SCALE_FACTOR), int(y / SCALE_FACTOR)


def _logical_to_physical(x: int, y: int) -> Tuple[int, int]:
    """
    Convert logical coordinates (WDA coordinates) to physical coordinates (screenshot coordinates).
    
    Args:
        x: Logical X coordinate.
        y: Logical Y coordinate.
    
    Returns:
        Tuple of (physical_x, physical_y).
    """
    return int(x * SCALE_FACTOR), int(y * SCALE_FACTOR)


def _get_wda_session_url(wda_url: str, session_id: Optional[str], endpoint: str) -> str:
    """Get the correct WDA URL for a session endpoint."""
    base = wda_url.rstrip("/")
    if session_id:
        return f"{base}/session/{session_id}/{endpoint}"
    else:
        return f"{base}/{endpoint}"


class IOSActionHandler:
    """Handles execution of actions for iOS devices."""

    def __init__(
        self,
        wda_url: str = "http://localhost:8100",
        session_id: Optional[str] = None,
    ):
        self.wda_url = wda_url
        self.session_id = session_id

    def tap(self, x: int, y: int, delay: float = 1.0) -> bool:
        """Tap at the specified coordinates."""
        try:
            import requests
            url = _get_wda_session_url(self.wda_url, self.session_id, "actions")

            actions = {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {"type": "pointerMove", "duration": 0, "x": x / SCALE_FACTOR, "y": y / SCALE_FACTOR},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": 100},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ]
            }

            response = requests.post(url, json=actions, timeout=15, verify=False)
            time.sleep(delay)
            return response.status_code in (200, 201)
        except Exception as e:
            print(f"Error tapping: {e}")
            return False

    def double_tap(self, x: int, y: int, delay: float = 1.0) -> bool:
        """Double tap at the specified coordinates."""
        try:
            import requests
            url = _get_wda_session_url(self.wda_url, self.session_id, "actions")

            actions = {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {"type": "pointerMove", "duration": 0, "x": x / SCALE_FACTOR, "y": y / SCALE_FACTOR},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": 100},
                            {"type": "pointerUp", "button": 0},
                            {"type": "pause", "duration": 100},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": 100},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ]
            }

            response = requests.post(url, json=actions, timeout=10, verify=False)
            time.sleep(delay)
            return response.status_code in (200, 201)
        except Exception as e:
            print(f"Error double tapping: {e}")
            return False

    def long_press(self, x: int, y: int, duration: float = 3.0, delay: float = 1.0) -> bool:
        """Long press at the specified coordinates."""
        try:
            import requests
            url = _get_wda_session_url(self.wda_url, self.session_id, "actions")

            duration_ms = int(duration * 1000)
            actions = {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "finger1",
                        "parameters": {"pointerType": "touch"},
                        "actions": [
                            {"type": "pointerMove", "duration": 0, "x": x / SCALE_FACTOR, "y": y / SCALE_FACTOR},
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": duration_ms},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ]
            }

            response = requests.post(url, json=actions, timeout=int(duration + 10), verify=False)
            time.sleep(delay)
            return response.status_code in (200, 201)
        except Exception as e:
            print(f"Error long pressing: {e}")
            return False

    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: Optional[float] = None,
        delay: float = 1.0,
    ) -> bool:
        """Swipe from start to end coordinates."""
        try:
            import requests

            if duration is None:
                dist_sq = (start_x - end_x) ** 2 + (start_y - end_y) ** 2
                duration = dist_sq / 1000000
                duration = max(0.3, min(duration, 2.0))

            url = _get_wda_session_url(self.wda_url, self.session_id, "wda/dragfromtoforduration")

            payload = {
                "fromX": start_x / SCALE_FACTOR,
                "fromY": start_y / SCALE_FACTOR,
                "toX": end_x / SCALE_FACTOR,
                "toY": end_y / SCALE_FACTOR,
                "duration": duration,
            }

            response = requests.post(url, json=payload, timeout=int(duration + 10), verify=False)
            time.sleep(delay)
            return response.status_code in (200, 201)
        except Exception as e:
            print(f"Error swiping: {e}")
            return False

    def back(self, delay: float = 1.0) -> bool:
        """
        Navigate back (swipe from left edge).
        
        Uses dynamic coordinates based on actual screen size instead of hardcoded values.
        """
        try:
            import requests
            url = _get_wda_session_url(self.wda_url, self.session_id, "wda/dragfromtoforduration")

            # Get screen size (logical coordinates)
            screen_width, screen_height = self.get_screen_size()
            
            # Calculate back gesture coordinates based on screen size
            # Swipe from left edge (x=0) to about 1/3 of screen width
            from_x = 0
            from_y = screen_height // 2  # Middle of screen vertically
            to_x = screen_width // 3  # About 1/3 of screen width
            to_y = from_y  # Same Y coordinate

            payload = {
                "fromX": from_x,
                "fromY": from_y,
                "toX": to_x,
                "toY": to_y,
                "duration": 0.3,
            }

            response = requests.post(url, json=payload, timeout=10, verify=False)
            time.sleep(delay)
            return response.status_code in (200, 201)
        except Exception as e:
            print(f"Error performing back gesture: {e}")
            return False

    def home(self, delay: float = 1.0) -> bool:
        """Press the home button."""
        try:
            import requests
            url = f"{self.wda_url.rstrip('/')}/wda/homescreen"
            response = requests.post(url, timeout=10, verify=False)
            time.sleep(delay)
            return response.status_code in (200, 201)
        except Exception as e:
            print(f"Error pressing home: {e}")
            return False

    def launch_app(self, app_name: str, delay: float = 1.0) -> bool:
        """Launch an app by name."""
        if app_name not in APP_PACKAGES_IOS:
            print(f"App '{app_name}' not found in APP_PACKAGES_IOS")
            return False

        try:
            import requests
            bundle_id = APP_PACKAGES_IOS[app_name]
            url = _get_wda_session_url(self.wda_url, self.session_id, "wda/apps/launch")

            response = requests.post(
                url, json={"bundleId": bundle_id}, timeout=10, verify=False
            )

            time.sleep(delay)
            return response.status_code in (200, 201)
        except Exception as e:
            print(f"Error launching app: {e}")
            return False

    def type_text(self, text: str, frequency: int = 60) -> bool:
        """Type text into the currently focused input field."""
        try:
            import requests
            url = _get_wda_session_url(self.wda_url, self.session_id, "wda/keys")

            response = requests.post(
                url, json={"value": list(text), "frequency": frequency}, timeout=30, verify=False
            )

            return response.status_code in (200, 201)
        except Exception as e:
            print(f"Error typing text: {e}")
            return False

    def clear_text(self) -> bool:
        """Clear text in the currently focused input field."""
        try:
            import requests
            url = _get_wda_session_url(self.wda_url, self.session_id, "element/active")

            response = requests.get(url, timeout=10, verify=False)

            if response.status_code == 200:
                data = response.json()
                element_id = data.get("value", {}).get("ELEMENT") or data.get("value", {}).get("element-6066-11e4-a52e-4f735466cecf")

                if element_id:
                    clear_url = _get_wda_session_url(self.wda_url, self.session_id, f"element/{element_id}/clear")
                    response = requests.post(clear_url, timeout=10, verify=False)
                    return response.status_code in (200, 201)

            return False
        except Exception as e:
            print(f"Error clearing text: {e}")
            return False

    def hide_keyboard(self) -> bool:
        """Hide the on-screen keyboard."""
        try:
            import requests
            url = f"{self.wda_url.rstrip('/')}/wda/keyboard/dismiss"
            response = requests.post(url, timeout=10, verify=False)
            return response.status_code in (200, 201)
        except Exception as e:
            print(f"Error hiding keyboard: {e}")
            return False

    def get_current_app(self) -> str:
        """Get the currently active app name."""
        try:
            import requests
            response = requests.get(
                f"{self.wda_url.rstrip('/')}/wda/activeAppInfo", timeout=5, verify=False
            )

            if response.status_code == 200:
                data = response.json()
                value = data.get("value", {})
                bundle_id = value.get("bundleId", "")

                if bundle_id:
                    for app_name, package in APP_PACKAGES_IOS.items():
                        if package == bundle_id:
                            return app_name

                return "System Home"

        except Exception as e:
            print(f"Error getting current app: {e}")

        return "System Home"

    def get_screen_size(self) -> tuple[int, int]:
        """Get the screen dimensions."""
        try:
            import requests
            url = _get_wda_session_url(self.wda_url, self.session_id, "window/size")

            response = requests.get(url, timeout=5, verify=False)

            if response.status_code == 200:
                data = response.json()
                value = data.get("value", {})
                width = value.get("width", 375)
                height = value.get("height", 812)
                return width, height

        except Exception as e:
            print(f"Error getting screen size: {e}")

        # Default iPhone screen size
        return 375, 812
