import cv2
import time
from ultralytics import YOLO

# ==========================================
# CONFIGURATION
# ==========================================
LOITERING_THRESHOLD_SEC = 6.0  # Seconds inside zone before loitering alert

model = YOLO("yolov8n.pt")
camera = cv2.VideoCapture(0)

# Mouse-drawn zone state
drawing = False
zone_start = None
zone_end = None

# Tracking entry timestamps: track_id -> timestamp
zone_occupants = {}

def draw_zone(event, x, y, flags, param):
    global drawing, zone_start, zone_end
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        zone_start = (x, y)
        zone_end = (x, y)
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            zone_end = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        zone_end = (x, y)

window_name = "SafeSight - Advanced Restricted Zone"
cv2.namedWindow(window_name)
cv2.setMouseCallback(window_name, draw_zone)

print("Advanced Restricted Zone Initialized. Draw with mouse. Press 'c' to clear, 'q' to quit.")

while True:
    success, frame = camera.read()
    if not success:
        print("Failed to read camera feed.")
        break

    curr_time = time.time()
    results = model.track(frame, persist=True, verbose=False)
    result = results[0]

    # Calculate Zone Rect Coordinates
    rz_x1, rz_y1, rz_x2, rz_y2 = None, None, None, None
    zone_active = zone_start is not None and zone_end is not None

    if zone_active:
        rz_x1 = min(zone_start[0], zone_end[0])
        rz_y1 = min(zone_start[1], zone_end[1])
        rz_x2 = max(zone_start[0], zone_end[0])
        rz_y2 = max(zone_start[1], zone_end[1])

    current_frame_ids = set()
    zone_breached = False

    if result.boxes.id is not None:
        boxes = result.boxes.xyxy.cpu().numpy()
        ids = result.boxes.id.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()

        for box, track_id, class_id, conf in zip(boxes, ids, classes, confs):
            track_id = int(track_id)
            if model.names[int(class_id)] != "person":
                continue

            current_frame_ids.add(track_id)
            x1, y1, x2, y2 = map(int, box)
            cx = (x1 + x2) // 2
            foot_y = y2  # Bottom edge of bounding box (feet location)

            # Check Intrusion using foot position
            inside = False
            if zone_active:
                inside = (rz_x1 <= cx <= rz_x2) and (rz_y1 <= foot_y <= rz_y2)

            box_color = (0, 255, 0)
            tag_text = f"ID:{track_id}"

            if inside:
                zone_breached = True
                box_color = (0, 0, 255)

                if track_id not in zone_occupants:
                    zone_occupants[track_id] = curr_time
                    print(f"🚨 INTRUSION BREACH: Person ID {track_id} entered zone.")

                dwell_time = curr_time - zone_occupants[track_id]
                
                if dwell_time >= LOITERING_THRESHOLD_SEC:
                    tag_text = f"ID:{track_id} | LOITERING ({dwell_time:.1f}s)"
                else:
                    tag_text = f"ID:{track_id} | INTRUSION ({dwell_time:.1f}s)"
            else:
                zone_occupants.pop(track_id, None)

            # Draw Person Bounding Box & Foot Anchor
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            cv2.circle(frame, (cx, foot_y), 5, (0, 255, 255), -1)
            cv2.putText(frame, tag_text, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)

    # Clean up departed IDs from zone tracking
    for stale_id in list(zone_occupants.keys()):
        if stale_id not in current_frame_ids:
            zone_occupants.pop(stale_id, None)

    # Draw Restricted Zone Perimeter
    if zone_active:
        zone_color = (0, 0, 255) if zone_breached else (255, 255, 255)
        cv2.rectangle(frame, (rz_x1, rz_y1), (rz_x2, rz_y2), zone_color, 2)
        cv2.putText(frame, "RESTRICTED PERIMETER", (rz_x1, max(rz_y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, zone_color, 2)

    # HUD Banner
    cv2.rectangle(frame, (10, 10), (320, 60), (20, 20, 20), -1)
    status_label = "ZONE STATUS: BREACHED" if zone_breached else "ZONE STATUS: SECURE"
    status_col = (0, 0, 255) if zone_breached else (0, 255, 0)
    cv2.putText(frame, status_label, (20, 42), cv2.FONT_HERSHEY_DUPLEX, 0.55, status_col, 1)

    cv2.imshow(window_name, frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('c'):
        zone_start, zone_end = None, None
        zone_occupants.clear()
        print("Zone cleared.")

camera.release()
cv2.destroyAllWindows()