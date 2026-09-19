import cv2
import time
from ultralytics import YOLO

model = YOLO("yolov8n.pt")
camera = cv2.VideoCapture(0)

prev_time = time.time()
print("SafeSight Data Inspector Active. Press 'q' to quit.")

while True:
    success, frame = camera.read()
    if not success:
        print("Failed to read camera feed.")
        break

    curr_time = time.time()
    fps = 1.0 / max(curr_time - prev_time, 0.001)
    prev_time = curr_time

    results = model(frame, verbose=False)
    result = results[0]

    # Semi-transparent side panel for parsed data
    h, w, _ = frame.shape
    panel_w = 320
    overlay = frame.copy()
    cv2.rectangle(overlay, (w - panel_w, 0), (w, h), (15, 15, 15), -1)
    cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

    cv2.putText(frame, "PARSED TENSOR DATA", (w - panel_w + 15, 30),
                cv2.FONT_HERSHEY_DUPLEX, 0.55, (0, 255, 255), 1)
    cv2.putText(frame, f"Frame FPS: {fps:.1f}", (w - panel_w + 15, 52),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
    cv2.line(frame, (w - panel_w + 15, 60), (w - 15, 60), (70, 70, 70), 1)

    y_offset = 85
    if result.boxes is not None and len(result.boxes) > 0:
        for idx, box in enumerate(result.boxes[:6]):  # Display first 6 detections
            cls_id = int(box.cls[0])
            label = model.names[cls_id]
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

            # Draw visual box on frame
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{label} ({conf:.2f})", (x1, max(y1 - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

            # Draw parsed telemetry in side panel
            cv2.putText(frame, f"#{idx+1} {label.upper()} ({conf*100:.0f}%)", (w - panel_w + 15, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            cv2.putText(frame, f"   Box: [{x1}, {y1}, {x2}, {y2}]", (w - panel_w + 15, y_offset + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1)
            cv2.putText(frame, f"   Dim: {x2-x1}w x {y2-y1}h px", (w - panel_w + 15, y_offset + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1)
            y_offset += 55
    else:
        cv2.putText(frame, "No targets detected", (w - panel_w + 15, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)

    cv2.imshow("SafeSight - Data Inspector", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

camera.release()
cv2.destroyAllWindows()