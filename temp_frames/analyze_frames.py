"""Analyze Manim video frames for visual bugs and issues."""
import cv2
import numpy as np
import os
from pathlib import Path

def analyze_frame(frame, frame_idx, timestamp):
    """Analyze single frame for visual issues."""
    issues = []
    
    # Convert to grayscale for analysis
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    
    # 1. Check for completely black frames (render failures)
    if np.mean(gray) < 5:
        issues.append(f"⚠️  BLACK FRAME at {timestamp:.2f}s (frame {frame_idx})")
    
    # 2. Check for completely white frames (overexposure)
    if np.mean(gray) > 250:
        issues.append(f"⚠️  WHITE FRAME at {timestamp:.2f}s (frame {frame_idx})")
    
    # 3. Check for text rendering issues (looking for broken LaTeX)
    # Use edge detection to find text regions
    edges = cv2.Canny(gray, 50, 150)
    text_density = np.sum(edges) / (height * width)
    
    # Abnormally high edge density might indicate broken rendering
    if text_density > 0.15:
        issues.append(f"⚠️  HIGH EDGE DENSITY at {timestamp:.2f}s (possible broken LaTeX/text)")
    
    # 4. Check for color anomalies (BGR channels imbalanced)
    b, g, r = cv2.split(frame)
    b_mean, g_mean, r_mean = np.mean(b), np.mean(g), np.mean(r)
    
    # If one channel dominates heavily, might be color bug
    max_channel = max(b_mean, g_mean, r_mean)
    if max_channel > 200 and (max_channel - min(b_mean, g_mean, r_mean)) > 150:
        issues.append(f"⚠️  COLOR IMBALANCE at {timestamp:.2f}s (dominant channel: {max_channel:.0f})")
    
    # 5. Check for graph clipping (values outside visible area)
    # Look at top/bottom 5% of frame for unexpected content
    top_region = gray[:int(height*0.05), :]
    bottom_region = gray[int(height*0.95):, :]
    
    if np.mean(top_region) > 50 or np.mean(bottom_region) > 50:
        # Might have clipped graphs
        pass  # This is too sensitive, skip for now
    
    return issues

def analyze_video_sequence(frames_dir):
    """Analyze sequence of frames for temporal issues."""
    frames = sorted(Path(frames_dir).glob("*.jpg"))
    
    print(f"\n=== ANALYZING {len(frames)} FRAMES ===\n")
    
    all_issues = []
    prev_frame = None
    
    for frame_path in frames:
        # Parse timestamp from filename
        parts = frame_path.stem.split("_")
        frame_idx = int(parts[1])
        timestamp = float(parts[2].replace("s", ""))
        
        frame = cv2.imread(str(frame_path))
        
        # Analyze individual frame
        issues = analyze_frame(frame, frame_idx, timestamp)
        all_issues.extend(issues)
        
        # Check for sudden jumps (scene cuts that might be unintended)
        if prev_frame is not None:
            diff = cv2.absdiff(frame, prev_frame)
            jump_score = np.mean(diff)
            
            if jump_score > 80:
                all_issues.append(f"⚠️  SUDDEN SCENE JUMP at {timestamp:.2f}s (diff: {jump_score:.1f})")
        
        prev_frame = frame
    
    return all_issues

def main():
    frames_dir = "temp_frames/analysis"
    
    if not os.path.exists(frames_dir):
        print(f"❌ Frames directory not found: {frames_dir}")
        return
    
    issues = analyze_video_sequence(frames_dir)
    
    print("\n=== ANALYSIS RESULTS ===\n")
    
    if not issues:
        print("✅ No visual bugs detected!")
    else:
        print(f"Found {len(issues)} potential issues:\n")
        for issue in issues:
            print(issue)
    
    # Additional metrics
    print("\n=== RECOMMENDATIONS ===\n")
    print("1. Check LaTeX rendering: Look for broken math symbols")
    print("2. Verify graph bounds: Ensure plots fit within axes")
    print("3. Review color consistency: Check for unintended color shifts")
    print("4. Validate transitions: Ensure smooth scene changes")

if __name__ == "__main__":
    main()
