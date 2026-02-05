"""iOS Screenshot Labeling - draw bounding boxes and labels on screenshots."""

import cv2
import os
from typing import List, Optional
from ios_agent.hierarchy import IOSElement

try:
    import pyshine as ps
except ImportError:
    # Fallback if pyshine is not available
    try:
        import puttext as ps
    except ImportError:
        ps = None

# iOS coordinate scale factor: XML bounds are in logical coordinates,
# but screenshots are in physical coordinates (typically 3x for modern iPhones)
IOS_SCALE_FACTOR = 3


def _get_scale_factor(img_path: str) -> float:
    """
    Calculate scale factor between logical coordinates and physical screenshot.
    
    Args:
        img_path: Path to screenshot.
    
    Returns:
        Scale factor (typically 3.0 for modern iPhones).
    """
    try:
        img = cv2.imread(img_path)
        if img is None:
            return IOS_SCALE_FACTOR
        
        height, width = img.shape[:2]
        
        # Common iPhone logical sizes
        # iPhone 14 Pro: logical 393x852, physical 1179x2556 (scale 3)
        # iPhone 13: logical 390x844, physical 1170x2532 (scale 3)
        # iPhone SE: logical 375x667, physical 750x1334 (scale 2)
        
        # Try to detect scale factor based on common ratios
        if width >= 1100:  # Likely physical coordinate (3x scale)
            # Try to match with logical sizes
            if abs(width / 3 - 393) < 10:  # iPhone 14 Pro
                return 3.0
            elif abs(width / 3 - 390) < 10:  # iPhone 13
                return 3.0
            elif abs(width / 2 - 375) < 10:  # iPhone SE (2x)
                return 2.0
            else:
                # Default: estimate scale factor
                return width / 375.0  # Assume logical width is 375
        else:
            # Likely already in logical coordinates
            return 1.0
    except Exception:
        return IOS_SCALE_FACTOR


def draw_bbox_multi_ios(
    img_path: str,
    output_path: str,
    elem_list: List[IOSElement],
    record_mode: bool = False,
    dark_mode: bool = False,
    scale_factor: Optional[float] = None
):
    """
    Draw bounding boxes and labels on iOS screenshot.
    
    Similar to Android-Lab's draw_bbox_multi, but for iOS elements.
    
    Args:
        img_path: Path to input screenshot.
        output_path: Path to save labeled screenshot.
        elem_list: List of IOSElement objects (bboxes in logical coordinates).
        record_mode: Whether to use record mode coloring.
        dark_mode: Whether to use dark mode colors.
        scale_factor: Optional scale factor to convert logical to physical coordinates.
                     If None, will be auto-detected from screenshot dimensions.
    """
    if not os.path.exists(img_path):
        print(f"Error: Image file not found: {img_path}")
        return None
    
    imgcv = cv2.imread(img_path)
    if imgcv is None:
        print(f"Error: Failed to read image: {img_path}")
        return None
    
    # Auto-detect scale factor if not provided
    if scale_factor is None:
        scale_factor = _get_scale_factor(img_path)
    
    count = 1
    for elem in elem_list:
        try:
            # Validate bbox before accessing
            if not elem.bbox or not isinstance(elem.bbox, (tuple, list)) or len(elem.bbox) < 2:
                # Skip elements with invalid bbox
                count += 1
                continue
            
            top_left = elem.bbox[0]
            bottom_right = elem.bbox[1]
            
            # Validate top_left and bottom_right are tuples/lists with 2 elements
            if not top_left or not bottom_right:
                count += 1
                continue
            
            if not isinstance(top_left, (tuple, list)) or len(top_left) < 2:
                count += 1
                continue
            
            if not isinstance(bottom_right, (tuple, list)) or len(bottom_right) < 2:
                count += 1
                continue
            
            # Convert logical coordinates to physical coordinates
            left = int(top_left[0] * scale_factor)
            top = int(top_left[1] * scale_factor)
            right = int(bottom_right[0] * scale_factor)
            bottom = int(bottom_right[1] * scale_factor)
            
            # Validate coordinates are valid numbers
            if not all(isinstance(coord, (int, float)) for coord in [left, top, right, bottom]):
                count += 1
                continue
            
            # Validate coordinates are within reasonable bounds (not NaN or inf)
            if any(not (isinstance(coord, (int, float)) and -1000000 < coord < 1000000) 
                   for coord in [left, top, right, bottom]):
                count += 1
                continue
            
            # Validate bbox has positive size
            if right <= left or bottom <= top:
                count += 1
                continue
            
            label = str(count)
            
            if record_mode:
                # Use different colors for different attribute types
                if elem.attrib == "clickable":
                    color = (250, 0, 0)  # Red for clickable
                elif elem.attrib == "focusable":
                    color = (0, 0, 250)  # Blue for focusable
                else:
                    color = (0, 250, 0)  # Green for others
                
                if ps:
                    imgcv = ps.putBText(
                        imgcv, label,
                        text_offset_x=(left + right) // 2 + 10,
                        text_offset_y=(top + bottom) // 2 + 10,
                        vspace=10, hspace=10, font_scale=1, thickness=2,
                        background_RGB=color, text_RGB=(255, 250, 250), alpha=0.5
                    )
                else:
                    # Fallback: use cv2.putText (should match Android's font_scale=1 for record_mode)
                    cv2.rectangle(imgcv, (left, top), (right, bottom), color, 2)
                    cv2.putText(imgcv, label, ((left + right) // 2, (top + bottom) // 2),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 250, 250), 2)
            else:
                # Normal mode
                text_color = (10, 10, 10) if dark_mode else (255, 250, 250)
                bg_color = (255, 250, 250) if dark_mode else (10, 10, 10)
                
                if ps:
                    imgcv = ps.putBText(
                        imgcv, label,
                        text_offset_x=(left + right) // 2 + 10,
                        text_offset_y=(top + bottom) // 2 + 10,
                        vspace=10, hspace=10, font_scale=2, thickness=2,
                        background_RGB=bg_color, text_RGB=text_color, alpha=0.5
                    )
                else:
                    # Fallback: use cv2.putText (should match Android's font_scale=2)
                    # Note: cv2.putText font_scale is different from pyshine, so we use 2 to match visual size
                    cv2.rectangle(imgcv, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(imgcv, label, ((left + right) // 2, (top + bottom) // 2),
                               cv2.FONT_HERSHEY_SIMPLEX, 2, text_color, 2)
        except Exception as e:
            print(f"ERROR: An exception occurs while labeling the image\n{e}")
        
        count += 1
    
    # Save labeled image
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, imgcv)
    return imgcv
