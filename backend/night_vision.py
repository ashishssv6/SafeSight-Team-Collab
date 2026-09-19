import cv2
import time

camera = cv2.VideoCapture(0)

# CLAHE setup: clipLimit limits noise amplification, tileGridSize defines local neighborhood
clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))

# Operational Modes: "NORMAL", "THERMAL", "NIGHT_VISION"
current_mode = "NORMAL"

print("=" * 60)
print("  SAFESIGHT MULTI-SPECTRAL VISION MODULE")
print("=" * 60)
print("  Press 't' -> Simulated Thermal Heatmap Mode")
print("  Press 'n' -> CLAHE Adaptive Low-Light Night-Vision Mode")
print("  Press 'o' -> Original Standard RGB Mode")
print("  Press 'q' -> Exit Module")
print("=" * 60)

prev_time = time.time()

while True:
    success, frame = camera.read()
    if not success:
        print("Camera feed unavailable.")
        break

    curr_time = time.time()
    fps = 1.0 / max(curr_time - prev_time, 0.001)
    prev_time = curr_time

    display_frame = frame.copy()

    # ----------------------------------------------------
    # 1. APPLY MULTI-SPECTRAL TRANSFORMATIONS
    # ----------------------------------------------------
    if current_mode == "THERMAL":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Apply Inferno false-color mapping (simulates infrared heat radiance)
        display_frame = cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
        mode_badge = "MODE: THERMAL INFRARED SIMULATION"
        badge_color = (0, 140, 255)

    elif current_mode == "NIGHT_VISION":
        # Convert BGR to LAB color space to isolate illumination (L-channel) from chroma (A, B)
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        
        # Apply CLAHE to the Luminance channel only
        enhanced_l = clahe.apply(l_channel)
        
        # Merge back and convert to BGR
        merged_lab = cv2.merge((enhanced_l, a_channel, b_channel))
        enhanced_bgr = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)
        
        # Add a subtle phosphor green tint typical of tactical night-vision goggles
        green_tint = enhanced_bgr.copy()
        green_tint[:, :, 0] = np_val = cv2.multiply(green_tint[:, :, 0], 0.7)  # Dim Blue
        green_tint[:, :, 2] = cv2.multiply(green_tint[:, :, 2], 0.7)          # Dim Red
        green_tint[:, :, 1] = cv2.add(green_tint[:, :, 1], 30)                # Boost Green
        
        display_frame = green_tint
        mode_badge = "MODE: CLAHE LOW-LIGHT NIGHT VISION"
        badge_color = (0, 255, 0)

    else:
        mode_badge = "MODE: STANDARD OPTICAL RGB"
        badge_color = (255, 255, 255)

    # ----------------------------------------------------
    # 2. HUD OVERLAY
    # ----------------------------------------------------
    cv2.rectangle(display_frame, (10, 10), (430, 75), (15, 15, 15), -1)
    cv2.putText(display_frame, "SAFESIGHT MULTI-SPECTRAL SENSOR", (20, 32),
                cv2.FONT_HERSHEY_DUPLEX, 0.48, (255, 255, 255), 1)
    cv2.putText(display_frame, f"FPS: {fps:.1f} | {mode_badge}", (20, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, badge_color, 1)

    cv2.imshow("SafeSight - Multi-Spectral Vision Stream", display_frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('t'):
        current_mode = "THERMAL"
    elif key == ord('n'):
        current_mode = "NIGHT_VISION"
    elif key == ord('o'):
        current_mode = "NORMAL"

camera.release()
cv2.destroyAllWindows()