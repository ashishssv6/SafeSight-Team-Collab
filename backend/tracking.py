import cv2
import math
import time
from ultralytics import YOLO

# ==========================================
# CONFIGURATION
# ==========================================
NORMALIZED_SPEED_LIMIT = 1.3    # Height-units moved per second for running
MIN_CONSECUTIVE_FRAMES = 3      # Frames to confirm sustained running
TRAIL_LENGTH = 20               # Points in movement trajectory tail

model = YOLO("yolov8n.pt")
camera = cv2.VideoCapture(0)

# Tracking state memory
tracker_positions = {}      # track_id -> (cx, cy, h, timestamp)
tracker_history = {}        # track_id -> [(cx, cy), ...]
high_speed_counters = {}    # track_id -> frame_count

prev_frame_time = time.time()
print("SafeSight Advanced Tracking Module Running. Press 'q' to quit.")

while True:
    success, frame = camera.read()
    if not success:
        print("Failed to read camera.")
        break

    curr_time = time.time()
    dt = max(curr_time - prev_frame_time, 0.001)
    prev_frame_time = curr_time

    results = model.track(frame, persist=True, verbose=False)
    result = results[0]

    current_frame_ids = set()

    if result.boxes.id is not None:
        boxes = result.boxes.xyxy.cpu().numpy()
        ids = result.boxes.id.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()

        for box, track_id, cls_id, conf in zip(boxes, ids, classes, confs):
            track_id = int(track_id)
            if model.names[int(cls_id)] != "person":
                continue

            current_frame_ids.add(track_id)
            x1, y1, x2, y2 = map(int, box)
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            h = max(y2 - y1, 1)

            # Compute Height-Normalized Speed
            norm_speed = 0.0
            if track_id in tracker_positions:
                old_cx, old_cy, old_h, old_time = tracker_positions[track_id]
                delta_sec = max(curr_time - old_time, 0.001)
                pixel_dist = math.hypot(cx - old_cx, cy - old_cy)
                norm_speed = (pixel_dist / h) / delta_sec

            tracker_positions[track_id] = (cx, cy, h, curr_time)

            # Store movement path
            if track_id not in tracker_history:
                tracker_history[track_id] = []
            tracker_history[track_id].append((cx, cy))
            if len(tracker_history[track_id]) > TRAIL_LENGTH:
                tracker_history[track_id].pop(0)

            # High Speed Filter
            if norm_speed > NORMALIZED_SPEED_LIMIT:
                high_speed_counters[track_id] = high_speed_counters.get(track_id, 0) + 1
            else:
                high_speed_counters[track_id] = 0

            is_running = high_speed_counters[track_id] >= MIN_CONSECUTIVE_FRAMES

            # Styling
            status_text = "SUDDEN RUNNING" if is_running else "NORMAL"
            box_color = (0, 0, 255) if is_running else (0, 255, 0)

            # Draw trajectory path
            for i in range(1, len(tracker_history[track_id])):
                pt1 = tracker_history[track_id][i - 1]
                pt2 = tracker_history[track_id][i]
                thickness = int(math.sqrt(TRAIL_LENGTH / float(i + 1)) * 2)
                cv2.line(frame, pt1, pt2, box_color, thickness)

            # Draw Person Bounding Box & HUD
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            caption = f"ID:{track_id} | Spd:{norm_speed:.1f}/s | {status_text}"
            cv2.putText(frame, caption, (x1, max(y1 - 8, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_color, 2)

    # Garbage collection for departed IDs
    for stale_id in list(tracker_positions.keys()):
        if stale_id not in current_frame_ids:
            tracker_positions.pop(stale_id, None)
            tracker_history.pop(stale_id, None)
            high_speed_counters.pop(stale_id, None)

    cv2.imshow("SafeSight - Multi-Object Behavioral Tracking", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

camera.release()
cv2.destroyAllWindows()