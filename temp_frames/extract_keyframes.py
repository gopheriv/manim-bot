import cv2
import os

# Extract keyframes from video
video_path = 'media/videos/taylor_sin_final/480p15/GenScene.mp4'
output_dir = 'temp_frames/analysis'

cap = cv2.VideoCapture(video_path)
os.makedirs(output_dir, exist_ok=True)

fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
duration = total_frames / fps

print(f"Video info:")
print(f"  FPS: {fps}")
print(f"  Frames: {total_frames}")
print(f"  Duration: {duration:.2f}s")
print(f"  Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

# Extract 20 keyframes evenly distributed
step = max(1, total_frames // 20)
frames_extracted = []
idx = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    if idx % step == 0:
        timestamp = idx / fps
        fname = f'{output_dir}/frame_{idx:04d}_{timestamp:.2f}s.jpg'
        cv2.imwrite(fname, frame)
        frames_extracted.append((idx, timestamp))
    
    idx += 1

cap.release()

print(f"\nExtracted {len(frames_extracted)} keyframes:")
for i, t in frames_extracted:
    print(f"  Frame {i}: {t:.2f}s")
