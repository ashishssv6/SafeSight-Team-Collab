import cv2
from ultralytics import YOLO
import math
import time
import numpy as np

# ==========================================
# CONFIGURATION
# ==========================================
CROWD_SIZE_THRESHOLD = 3      # Minimum people standing close to form a crowd
PROXIMITY_DISTANCE_PX = 200   # Max pixel distance between two people to be in same group
CROWD_DURATION_SEC = 5.0      # Seconds the group must stay together
GRACE_PERIOD_SEC = 1.5        # Buffer time before resetting timer on momentary tracking loss

model = YOLO("yolov8n.pt")
camera = cv2.VideoCapture(0)

crowd_start_time = None
last_seen_crowd_time = None
is_alert_triggered = False

while True:
    success, frame = camera.read()
    if not success:
        print("Failed to read camera feed.")
        break

    curr_time = time.time()
    results = model.track(frame, persist=True, verbose=False)
    result = results[0]

    person_centers = []
    person_boxes = []

    # 1. Extract Person Coordinates
    if result.boxes.id is not None:
        boxes = result.boxes.xyxy.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy()

        for box, cls_id in zip(boxes, classes):
            if model.names[int(cls_id)] == "person":
                x1, y1, x2, y2 = map(int, box)
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                person_centers.append((cx, cy))
                person_boxes.append((x1, y1, x2, y2))

    # 2. Advanced Spatial Clustering (Are people standing near each other?)
    crowd_clusters = []
    num_people = len(person_centers)

    for i in range(num_people):
        cluster = {i}
        for j in range(num_people):
            if i != j:
                dist = math.hypot(
                    person_centers[i][0] - person_centers[j][0],
                    person_centers[i][1] - person_centers[j][1]
                )
                if dist <= PROXIMITY_DISTANCE_PX:
                    cluster.add(j)
        if len(cluster) >= CROWD_SIZE_THRESHOLD:
            crowd_clusters.append(cluster)

    # Check if any valid spatial crowd exists
    has_crowd = len(crowd_clusters) > 0

    # 3. Temporal Gathering State Machine
    if has_crowd:
        last_seen_crowd_time = curr_time
        if crowd_start_time is None:
            crowd_start_time = curr_time
        
        crowd_duration = curr_time - crowd_start_time
        
        if crowd_duration >= CROWD_DURATION_SEC:
            status_text = f"🚨 PROLONGED CROWD GATHERING ({crowd_duration:.1f}s)"
            status_color = (0, 0, 255)  # Red
        else:
            status_text = f"⚠️ CROWD FORMING ({crowd_duration:.1f}s / {CROWD_DURATION_SEC}s)"
            status_color = (0, 165, 255)  # Orange
    else:
        # Grace period check: Don't instantly drop the timer if tracking blinks
        if last_seen_crowd_time and (curr_time - last_seen_crowd_time < GRACE_PERIOD_SEC):
            crowd_duration = curr_time - crowd_start_time if crowd_start_time else 0
            status_text = f"⚠️ TRACKING RECOVERY ({crowd_duration:.1f}s)"
            status_color = (0, 215, 255)
        else:
            crowd_start_time = None
            crowd_duration = 0.0
            status_text = "STATUS: NORMAL"
            status_color = (0, 255, 0)  # Green

    # 4. Visual Annotations & Proximity Network
    # Draw boxes
    for x1, y1, x2, y2 in person_boxes:
        cv2.rectangle(frame, (x1, y1), (x2, y2), status_color, 2)

    # Draw proximity connection lines between people in the same cluster
    for cluster in crowd_clusters:
        indices = list(cluster)
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                p1 = person_centers[indices[i]]
                p2 = person_centers[indices[j]]
                cv2.line(frame, p1, p2, (0, 0, 255), 2)

    # 5. Clean HUD Display
    cv2.rectangle(frame, (10, 10), (450, 90), (30, 30, 30), -1)
    cv2.putText(frame, f"Active People: {num_people}", (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(frame, status_text, (20, 68),
                cv2.FONT_HERSHEY_DUPLEX, 0.6, status_color, 2)

    cv2.imshow("SafeSight - Advanced Crowd Analysis", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

camera.release()
cv2.destroyAllWindows()