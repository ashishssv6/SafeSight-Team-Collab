import cv2
import time

camera = cv2.VideoCapture(0)

# Retrieve hardware properties
width = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
hw_fps = camera.get(cv2.CAP_PROP_FPS)

print("=" * 45)
print("  SAFESIGHT CAMERA HARDWARE DIAGNOSTICS")
print("=" * 45)
print(f"  Resolution : {width} x {height}")
print(f"  Sensor FPS : {hw_fps}")
print("  Status     : Stream Active")
print("=" * 45)
print("Press 'q' to exit diagnostic feed.")

prev_time = time.time()

while True:
    success, frame = camera.read()
    if not success:
        print("Camera feed disconnected or inaccessible.")
        break

    curr_time = time.time()
    fps = 1.0 / max(curr_time - prev_time, 0.001)
    prev_time = curr_time

    # Diagnostic HUD Overlay
    cv2.rectangle(frame, (10, 10), (280, 75), (20, 20, 20), -1)
    cv2.putText(frame, "HARDWARE DIAGNOSTIC", (20, 32),
                cv2.FONT_HERSHEY_DUPLEX, 0.45, (0, 255, 0), 1)
    cv2.putText(frame, f"Live FPS: {fps:.1f} | Res: {width}x{height}", (20, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)

    cv2.imshow("SafeSight - Camera Hardware Diagnostics", frame)

    key = cv2.waitKey(1) & 0xFF
    if key in (ord('q'), ord('Q')):
        break

camera.release()
cv2.destroyAllWindows()