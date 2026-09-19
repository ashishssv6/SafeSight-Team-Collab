import cv2
import time
import numpy as np

# ==========================================
# CALIBRATED ANTI-TAMPER THRESHOLDS
# ==========================================
TAMPER_CONFIRM_SEC = 1.8  # Seconds of continuous cover to trigger alert

camera = cv2.VideoCapture(0)
tamper_start_time = None
is_tampered = False

print("SafeSight Multi-Vector Anti-Tamper Engine Running.")
print("Test with white/ruled paper, hand, or dark cover. Press 'q' to exit.\n")

while True:
    success, frame = camera.read()
    if not success:
        print("Camera feed unavailable.")
        break

    curr_time = time.time()
    
    # 1. Grayscale & HSV Color Space Conversions
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # 2. Extract Mathematical Descriptors
    mean_bright = float(np.mean(gray))
    std_dev = float(np.std(gray))
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_saturation = float(np.mean(hsv[:, :, 1]))  # 0 to 255 (Color richness)

    # ----------------------------------------------------
    # 3. MULTI-VECTOR OCCLUSION DETECTION LOGIC
    # ----------------------------------------------------
    # Vector A: Dark Obstruction (Hand, Black Tape, Box)
    is_blackout = mean_bright < 25.0
    
    # Vector B: Laser / Light Blinding
    is_blinded = mean_bright > 235.0

    # Vector C: Solid Color / Smooth Surface (Cloth, Wall, Grease)
    is_low_texture = laplacian_var < 55.0 and std_dev < 22.0

    # Vector D: White / Ruled / Lined Paper / Notebook Cover
    # (High brightness, low saturation, limited edge variance)
    is_paper_or_sheet = (mean_bright > 120.0) and (mean_saturation < 40.0) and (laplacian_var < 220.0) and (std_dev < 48.0)

    # Unified Tamper Boolean
    tamper_detected = is_blackout or is_blinded or is_low_texture or is_paper_or_sheet

    # ----------------------------------------------------
    # 4. TEMPORAL PERSISTENCE (DEBOUNCE TIMER)
    # ----------------------------------------------------
    if tamper_detected:
        if tamper_start_time is None:
            tamper_start_time = curr_time
        
        tamper_duration = curr_time - tamper_start_time
        if tamper_duration >= TAMPER_CONFIRM_SEC:
            is_tampered = True
            tamper_msg = f"🚨 TAMPERED: LENS OBSTRUCTED ({tamper_duration:.1f}s)"
            hud_color = (0, 0, 255) # Red
        else:
            is_tampered = False
            tamper_msg = f"⚠️ OBSTRUCTION VERIFYING ({tamper_duration:.1f}s)"
            hud_color = (0, 140, 255) # Orange
    else:
        tamper_start_time = None
        is_tampered = False
        tamper_msg = "LENS STATUS: OPTICALLY CLEAR"
        hud_color = (0, 255, 0) # Green

    # ----------------------------------------------------
    # 5. DIAGNOSTIC HUD DISPLAY
    # ----------------------------------------------------
    cv2.rectangle(frame, (10, 10), (480, 130), (15, 15, 15), -1)
    cv2.putText(frame, "SAFESIGHT OPTICAL INTEGRITY", (20, 32),
                cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1)
    
    cv2.putText(frame, f"Laplacian Var: {laplacian_var:.1f} | StdDev: {std_dev:.1f}",
                (20, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)
    cv2.putText(frame, f"Brightness: {mean_bright:.1f} | Saturation: {mean_saturation:.1f}",
                (20, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)
    
    cv2.putText(frame, tamper_msg, (20, 110),
                cv2.FONT_HERSHEY_DUPLEX, 0.58, hud_color, 2)

    # Full frame flashing alert border
    if is_tampered:
        cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 255), 10)

    cv2.imshow("SafeSight - Calibrated Tamper Test", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

camera.release()
cv2.destroyAllWindows()