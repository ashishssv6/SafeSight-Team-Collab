import cv2
from ultralytics import YOLO
import math
import time

# ==========================================
# CONFIGURATION
# ==========================================
BAG_CLASSES = ["backpack", "handbag", "suitcase"]
OWNER_PROXIMITY_RADIUS_PX = 180   # Distance to consider owner standing near bag
ABANDONED_TIME_SEC = 5.0          # Seconds bag must be alone before alarm
STATIONARY_MOVE_LIMIT = 6.0       # Max pixel jitter to consider bag stationary

model = YOLO("yolov8n.pt")
camera = cv2.VideoCapture(0)

# Memory dictionaries
bag_positions = {}       # bag_track_id -> (cx, cy)
bag_stationary_start = {}# bag_track_id -> timestamp when it became stationary
bag_alone_start = {}     # bag_track_id -> timestamp when owner moved away

print("Advanced Abandoned Luggage Detection Initialized. Press 'q' to quit.")

while True:
    success, frame = camera.read()
    if not success:
        print("Failed to read camera feed.")
        break

    curr_time = time.time()
    results = model.track(frame, persist=True, verbose=False)
    result = results[0]

    people_coords = []
    detected_bags = {}

    if result.boxes.id is not None:
        boxes = result.boxes.xyxy.cpu().numpy()
        ids = result.boxes.id.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()

        for box, track_id, cls_id, conf in zip(boxes, ids, classes, confs):
            track_id = int(track_id)
            cls_name = model.names[int(cls_id)]
            x1, y1, x2, y2 = map(int, box)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            # 1. Collect all people locations
            if cls_name == "person":
                people_coords.append((cx, cy))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"Person {track_id}", (x1, y1 - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

            # 2. Collect all bag-like objects
            elif cls_name in BAG_CLASSES:
                detected_bags[track_id] = {
                    "box": (x1, y1, x2, y2),
                    "center": (cx, cy),
                    "label": cls_name,
                    "conf": conf
                }

    # Process each detected bag
    for bag_id, bdata in detected_bags.items():
        bx, by = bdata["center"]
        x1, y1, x2, y2 = bdata["box"]

        # Check if bag moved from previous position
        movement = 0.0
        if bag_id in bag_positions:
            old_bx, old_by = bag_positions[bag_id]
            movement = math.hypot(bx - old_bx, by - old_by)

        bag_positions[bag_id] = (bx, by)

        # Track stationary duration
        if movement < STATIONARY_MOVE_LIMIT:
            if bag_id not in bag_stationary_start:
                bag_stationary_start[bag_id] = curr_time
        else:
            bag_stationary_start.pop(bag_id, None)
            bag_alone_start.pop(bag_id, None)

        # Calculate distance to nearest person
        min_dist_to_person = float("inf")
        for px, py in people_coords:
            dist = math.hypot(px - bx, py - by)
            if dist < min_dist_to_person:
                min_dist_to_person = dist

        # Check owner presence
        is_stationary = bag_id in bag_stationary_start
        has_nearby_owner = min_dist_to_person <= OWNER_PROXIMITY_RADIUS_PX

        status_text = "BAG ATTENDED"
        status_color = (0, 255, 255) # Yellow

        if is_stationary and not has_nearby_owner:
            if bag_id not in bag_alone_start:
                bag_alone_start[bag_id] = curr_time

            alone_duration = curr_time - bag_alone_start[bag_id]

            if alone_duration >= ABANDONED_TIME_SEC:
                status_text = f"🚨 ABANDONED BAG ({alone_duration:.1f}s)"
                status_color = (0, 0, 255) # Red
            else:
                status_text = f"⚠️ OWNER AWAY ({alone_duration:.1f}s)"
                status_color = (0, 140, 255) # Orange
        else:
            bag_alone_start.pop(bag_id, None)

        # Draw bag marker and status
        cv2.rectangle(frame, (x1, y1), (x2, y2), status_color, 2)
        cv2.putText(frame, f"{bdata['label']} #{bag_id}", (x1, y1 - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_color, 1)
        cv2.putText(frame, status_text, (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_color, 2)

        # Draw proximity circle around stationary bag
        cv2.circle(frame, (bx, by), OWNER_PROXIMITY_RADIUS_PX, (255, 255, 255), 1)

    # Clean up disappeared bags
    for old_id in list(bag_positions.keys()):
        if old_id not in detected_bags:
            bag_positions.pop(old_id, None)
            bag_stationary_start.pop(old_id, None)
            bag_alone_start.pop(old_id, None)

    cv2.imshow("SafeSight - Advanced Abandoned Bag Detection", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

camera.release()
cv2.destroyAllWindows()