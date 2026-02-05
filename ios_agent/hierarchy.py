"""iOS UI Hierarchy - get and parse iOS page source for element labeling."""

import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class IOSElement:
    """Represents an iOS UI element."""
    uid: str
    bbox: Tuple[Tuple[int, int], Tuple[int, int]]  # ((x1, y1), (x2, y2))
    attrib: str  # "clickable" or "focusable"
    element_type: str  # XCUIElementTypeButton, etc.
    name: Optional[str] = None
    label: Optional[str] = None
    identifier: Optional[str] = None


def get_page_source(
    wda_url: str = "http://localhost:8100",
    session_id: Optional[str] = None,
    timeout: int = 10
) -> Optional[str]:
    """
    Get iOS page source (XML hierarchy) via WebDriverAgent.
    
    This function uses WebDriverAgent's /source endpoint to get the XML representation
    of the current UI hierarchy. It handles various response formats and provides
    robust error handling.
    
    Args:
        wda_url: WebDriverAgent URL.
        session_id: Optional WDA session ID (recommended for better reliability).
        timeout: Request timeout in seconds.
    
    Returns:
        XML string of the page source, or None if failed.
    """
    try:
        import requests
        
        # Try with session ID first (more reliable)
        urls_to_try = []
        if session_id:
            urls_to_try.append(f"{wda_url.rstrip('/')}/session/{session_id}/source")
        # Also try without session ID as fallback
        urls_to_try.append(f"{wda_url.rstrip('/')}/source")
        
        last_error = None
        for url in urls_to_try:
            try:
                response = requests.get(url, timeout=timeout, verify=False)
                
                if response.status_code == 200:
                    # Try to parse as JSON first (WDA typically returns JSON)
                    try:
                        data = response.json()
                        source = None
                        
                        # WebDriverAgent returns source in different formats
                        # Standard format: {"value": "<xml>...</xml>"}
                        if isinstance(data, dict):
                            # Try different possible keys
                            source = data.get("value")
                            
                            # If value is a dict, try to extract source from it
                            if isinstance(source, dict):
                                source = source.get("source") or source.get("value")
                            
                            # If still not found, try other keys
                            if source is None:
                                source = data.get("source")
                            
                            # If value is a dict containing source
                            if source is None and isinstance(data.get("value"), dict):
                                source = data.get("value", {}).get("source")
                            
                            # If source is still a dict, try to get XML from it
                            if isinstance(source, dict):
                                source = source.get("source") or source.get("value")
                        else:
                            # If not a dict, try to convert to string
                            source = str(data) if data else None
                        
                        # Process the source string
                        if source and isinstance(source, str) and len(source.strip()) > 0:
                            # Remove surrounding quotes if present
                            source = source.strip()
                            if (source.startswith('"') and source.endswith('"')) or \
                               (source.startswith("'") and source.endswith("'")):
                                source = source[1:-1]
                            
                            # Unescape common escape sequences
                            source = source.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
                            source = source.replace('\\"', '"').replace("\\'", "'")
                            
                            # Validate that source is actually XML-like
                            source_stripped = source.strip()
                            if source_stripped.startswith('<') or '<?xml' in source_stripped[:100]:
                                # Validate it's valid XML by trying to parse it
                                try:
                                    ET.fromstring(source_stripped)
                                    return source
                                except ET.ParseError:
                                    # Might still be valid XML, just try to return it
                                    # The parser will handle it later
                                    print(f"Warning: XML from {url} may have parsing issues, but returning it anyway")
                                    return source
                            else:
                                # Debug: print first 200 chars to see what we got
                                preview = source[:200].replace('\n', '\\n')
                                print(f"Warning: Page source doesn't look like XML from {url}")
                                print(f"  Preview: {preview}...")
                                # Still return it, let parser handle it
                                return source
                        else:
                            print(f"Warning: Empty or invalid page source from {url}")
                            print(f"  Response data type: {type(data)}")
                            print(f"  Response preview: {str(response.text)[:500]}")
                            
                    except ValueError as e:
                        # Not JSON, try as text/XML directly
                        if response.text and len(response.text.strip()) > 0:
                            text = response.text.strip()
                            if text.startswith('<') or '<?xml' in text[:100]:
                                print(f"✓ Got XML directly as text from {url}")
                                return text
                            else:
                                print(f"Warning: Response is not JSON and doesn't look like XML from {url}")
                                print(f"  Response preview: {text[:200]}")
                        else:
                            print(f"Warning: Empty response text from {url}")
                            
                elif response.status_code == 404:
                    # Endpoint not found, try next URL
                    print(f"Warning: Endpoint not found (404) at {url}, trying next...")
                    continue
                elif response.status_code == 500:
                    # Server error, might be temporary
                    error_msg = f"Server error (500) from {url}"
                    print(f"Warning: {error_msg}")
                    last_error = error_msg
                    continue
                else:
                    error_msg = f"HTTP {response.status_code} getting page source from {url}"
                    print(f"Warning: {error_msg}")
                    print(f"  Response: {response.text[:200]}")
                    last_error = error_msg
                    continue
                    
            except requests.exceptions.Timeout:
                error_msg = f"Timeout getting page source from {url} (timeout={timeout}s)"
                print(f"Warning: {error_msg}")
                last_error = error_msg
                continue
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error getting page source from {url}: {e}"
                print(f"Warning: {error_msg}")
                last_error = error_msg
                continue
            except Exception as e:
                error_msg = f"Error getting page source from {url}: {e}"
                print(f"Warning: {error_msg}")
                import traceback
                traceback.print_exc()
                last_error = error_msg
                continue
        
        # If we get here, all URLs failed
        if last_error:
            print(f"❌ Error: Failed to get page source from all URLs. Last error: {last_error}")
            print(f"   Tried URLs: {urls_to_try}")
            print(f"   Make sure WebDriverAgent is running and accessible at {wda_url}")
            if session_id:
                print(f"   Session ID: {session_id}")
        return None
        
    except ImportError:
        print("❌ Error: requests library required. Install: pip install requests")
        return None
    except Exception as e:
        print(f"❌ Error getting page source: {e}")
        import traceback
        traceback.print_exc()
        return None


def parse_bounds(bounds_str: str) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """
    Parse bounds string from iOS XML.
    
    iOS bounds format: "{{x, y}, {width, height}}" or "x,y,width,height"
    
    Args:
        bounds_str: Bounds string from iOS XML.
    
    Returns:
        Tuple of ((x1, y1), (x2, y2)) or None if parsing fails.
    """
    if not bounds_str:
        return None
        
    try:
        # Try iOS format: {{x, y}, {width, height}}
        if "{{" in bounds_str:
            # Remove braces and parse
            bounds_str = bounds_str.replace("{{", "").replace("}}", "").replace("{", "").replace("}", "")
            parts = bounds_str.split(",")
            if len(parts) >= 4:
                x = int(float(parts[0].strip()))
                y = int(float(parts[1].strip()))
                width = int(float(parts[2].strip()))
                height = int(float(parts[3].strip()))
                return ((x, y), (x + width, y + height))
        
        # Try simple format: x,y,width,height
        parts = bounds_str.split(",")
        if len(parts) >= 4:
            x = int(float(parts[0].strip()))
            y = int(float(parts[1].strip()))
            width = int(float(parts[2].strip()))
            height = int(float(parts[3].strip()))
            return ((x, y), (x + width, y + height))
        
        return None
    except Exception as e:
        print(f"Error parsing bounds '{bounds_str}': {e}")
        return None


def get_element_bounds(element: ET.Element) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """
    Get bounds from an iOS XML element.
    
    iOS XML can have bounds in two formats:
    1. As a 'bounds' attribute: "{{x, y}, {width, height}}"
    2. As separate attributes: x, y, width, height
    
    Args:
        element: XML element.
    
    Returns:
        Tuple of ((x1, y1), (x2, y2)) or None if not available.
    """
    # First, try to get bounds from 'bounds' attribute
    bounds_str = element.get('bounds', '')
    if bounds_str:
        bbox = parse_bounds(bounds_str)
        if bbox:
            return bbox
    
    # If no 'bounds' attribute, try to get from separate x, y, width, height attributes
    try:
        x_str = element.get('x', '')
        y_str = element.get('y', '')
        width_str = element.get('width', '')
        height_str = element.get('height', '')
        
        if x_str and y_str and width_str and height_str:
            x = int(float(x_str))
            y = int(float(y_str))
            width = int(float(width_str))
            height = int(float(height_str))
            return ((x, y), (x + width, y + height))
    except (ValueError, TypeError):
        pass
    
    return None


def get_element_id(element: ET.Element) -> str:
    """
    Generate a unique ID for an iOS element.
    
    Args:
        element: XML element.
    
    Returns:
        Unique identifier string.
    """
    # Get element type
    element_type = element.tag if hasattr(element, 'tag') else element.get('type', 'Unknown')
    
    # Get bounds for size
    bbox = get_element_bounds(element)
    if bbox:
        elem_w = bbox[1][0] - bbox[0][0]
        elem_h = bbox[1][1] - bbox[0][1]
    else:
        elem_w, elem_h = 0, 0
    
    # Try to use identifier or name
    identifier = element.get('name') or element.get('identifier') or element.get('label', '')
    
    if identifier:
        elem_id = f"{element_type}_{identifier.replace(' ', '_').replace(':', '_')}"
    else:
        elem_id = f"{element_type}_{elem_w}_{elem_h}"
    
    return elem_id


def is_interactive_element(element: ET.Element) -> bool:
    """
    Check if an iOS element is interactive (clickable/focusable).
    
    Args:
        element: XML element.
    
    Returns:
        True if element is interactive.
    """
    # iOS interactive element types
    interactive_types = [
        'XCUIElementTypeButton',
        'XCUIElementTypeCell',
        'XCUIElementTypeTextField',
        'XCUIElementTypeSecureTextField',
        'XCUIElementTypeSearchField',
        'XCUIElementTypeSlider',
        'XCUIElementTypeSwitch',
        'XCUIElementTypeTab',
        'XCUIElementTypeLink',
        'XCUIElementTypeImage',
        'XCUIElementTypeIcon',  # iOS app icons on home screen
        'XCUIElementTypeStaticText',  # Sometimes clickable
    ]
    
    element_type = element.tag if hasattr(element, 'tag') else element.get('type', '')
    
    # Check if type is in interactive types list
    is_interactive_type = any(interactive_type in element_type for interactive_type in interactive_types)
    
    # If not an interactive type, return False early
    if not is_interactive_type:
        return False
    
    # Check enabled attribute
    enabled = element.get('enabled', 'true')
    if enabled == 'false':
        return False
    
    # Check visible attribute (important for iOS)
    visible = element.get('visible', 'true')
    if visible == 'false':
        return False
    
    # Check if has valid bounds with actual size
    bbox = get_element_bounds(element)
    if not bbox:
        return False
    
    # Check if bounds have actual size (width and height > 0)
    x1, y1 = bbox[0]
    x2, y2 = bbox[1]
    width = x2 - x1
    height = y2 - y1
    
    # Element must have non-zero size to be interactive
    if width <= 0 or height <= 0:
        return False
    
    # Additional check: if bounds are all zeros, it's not visible
    if x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0:
        return False
    
    return True


def traverse_ios_tree(
    xml_string: str,
    elem_list: List[IOSElement],
    attrib: str = "clickable",
    add_index: bool = False
):
    """
    Traverse iOS XML tree and extract interactive elements.
    
    Args:
        xml_string: XML string from iOS page source.
        elem_list: List to append elements to.
        attrib: Attribute type ("clickable" or "focusable").
        add_index: Whether to add index to element ID.
    """
    try:
        root = ET.fromstring(xml_string)
        # print(f"  XML parsed successfully, root tag: {root.tag}")  # Commented out XML logs
    except ET.ParseError as e:
        # print(f"Error parsing XML (ParseError): {e}")  # Commented out XML logs
        # print(f"  XML preview (first 500 chars): {xml_string[:500]}")  # Commented out XML logs
        return
    except Exception as e:
        # print(f"Error parsing XML: {e}")  # Commented out XML logs
        # print(f"  XML preview (first 500 chars): {xml_string[:500]}")  # Commented out XML logs
        return
    
    def traverse(node, path=[]):
        """Recursive traversal."""
        path = path + [node]
        
        # Check if element is interactive
        if is_interactive_element(node):
            bbox = get_element_bounds(node)
            
            if bbox:
                # Calculate center
                center = ((bbox[0][0] + bbox[1][0]) // 2, (bbox[0][1] + bbox[1][1]) // 2)
                
                # Check if element is too close to existing elements
                close = False
                for e in elem_list:
                    e_bbox = e.bbox
                    e_center = ((e_bbox[0][0] + e_bbox[1][0]) // 2, 
                               (e_bbox[0][1] + e_bbox[1][1]) // 2)
                    dist = ((center[0] - e_center[0]) ** 2 + 
                           (center[1] - e_center[1]) ** 2) ** 0.5
                    if dist <= 5:
                        close = True
                        break
                
                if not close:
                    # Generate element ID
                    elem_id = get_element_id(node)
                    
                    # Add parent prefix if needed
                    if len(path) > 1:
                        parent_id = get_element_id(path[-2])
                        elem_id = f"{parent_id}_{elem_id}"
                    
                    if add_index:
                        index = node.get('index', '0')
                        elem_id += f"_{index}"
                    
                    # Create element
                    element = IOSElement(
                        uid=elem_id,
                        bbox=bbox,
                        attrib=attrib,
                        element_type=node.tag if hasattr(node, 'tag') else node.get('type', ''),
                        name=node.get('name'),
                        label=node.get('label'),
                        identifier=node.get('identifier')
                    )
                    elem_list.append(element)
        
        # Traverse children
        for child in node:
            traverse(child, path)
    
    traverse(root)


def get_ios_elements(xml_string: str) -> List[IOSElement]:
    """
    Extract interactive elements from iOS XML.
    
    Args:
        xml_string: XML string from iOS page source.
    
    Returns:
        List of IOSElement objects.
    """
    if not xml_string or len(xml_string.strip()) == 0:
        # print("Warning: Empty XML string provided to get_ios_elements")  # Commented out XML logs
        return []
    
    clickable_list = []
    focusable_list = []
    
    # Extract clickable elements (buttons, cells, etc.)
    # print(f"  Extracting clickable elements from XML ({len(xml_string)} chars)...")  # Commented out XML logs
    traverse_ios_tree(xml_string, clickable_list, "clickable", True)
    # print(f"  Found {len(clickable_list)} clickable elements")  # Commented out XML logs
    
    # Extract focusable elements (text fields, etc.)
    # print(f"  Extracting focusable elements from XML...")  # Commented out XML logs
    traverse_ios_tree(xml_string, focusable_list, "focusable", True)
    # print(f"  Found {len(focusable_list)} focusable elements")  # Commented out XML logs
    
    # Merge lists, avoiding duplicates
    elem_list = []
    for elem in clickable_list:
        elem_list.append(elem)
    
    for elem in focusable_list:
        bbox = elem.bbox
        center = ((bbox[0][0] + bbox[1][0]) // 2, (bbox[0][1] + bbox[1][1]) // 2)
        close = False
        for e in clickable_list:
            e_bbox = e.bbox
            e_center = ((e_bbox[0][0] + e_bbox[1][0]) // 2, 
                       (e_bbox[0][1] + e_bbox[1][1]) // 2)
            dist = ((center[0] - e_center[0]) ** 2 + 
                   (center[1] - e_center[1]) ** 2) ** 0.5
            if dist <= 10:
                close = True
                break
        if not close:
            elem_list.append(elem)
    
    # print(f"  Total elements after merging: {len(elem_list)}")  # Commented out XML logs
    return elem_list
