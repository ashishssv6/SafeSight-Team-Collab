import cv2
import time
from ultralytics import YOLO

# ==========================================
# CONFIGURATION
# ==========================================
CONF_THRESHOLD = 0.45
SECURITY_CLASSES = ["person", "backpack", "handbag", "suitcase", "laptop", "cell phone"]

model = YOLO("yolov8n.pt")
camera = cv2.VideoCapture(0)

# Performance counters
prev_time = time.time()
frame_count = 0

print("Advanced SafeSight Detection Module Running. Press 'q' to exit.")

while True:
    success, frame = camera.read()
    if not success:
        print("Failed to read camera stream.")
        break

    curr_time = time.time()
    fps = 1.0 / max(curr_time - prev_time, 0.001)
    prev_time = curr_time

    # Run inference with confidence filtering
    results = model(frame, conf=CONF_THRESHOLD, verbose=False)
    result = results[0]

    detected_counts = {}

    if result.boxes is not None:
        boxes = result.boxes.xyxy.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()

        for box, cls_id, conf in zip(boxes, classes, confidences):
            label = model.names[int(cls_id)]
            
            # Security class filter
            if label not in SECURITY_CLASSES:
                continue

            detected_counts[label] = detected_counts.get(label, 0) + 1
            x1, y1, x2, y2 = map(int, box)

            # Assign color coding
            color = (0, 255, 0) if label == "person" else (255, 140, 0)

            # Draw sleek bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            caption = f"{label.upper()} {conf:.2f}"
            cv2.putText(frame, caption, (x1, max(y1 - 8, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Information HUD Card
    cv2.rectangle(frame, (10, 10), (320, 95), (25, 25, 25), -1)
    cv2.putText(frame, "SAFESIGHT | DETECTION ENGINE", (20, 32),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(frame, f"FPS: {fps:.1f} | Conf: {CONF_THRESHOLD}", (20, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

    summary_text = ", ".join([f"{k}: {v}" for k, v in detected_counts.items()]) if detected_counts else "No targets in frame"
    cv2.putText(frame, summary_text[:35], (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    cv2.imshow("SafeSight - AI Detection Module", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

camera.release()
cv2.destroyAllWindows()