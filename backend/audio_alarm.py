import cv2
import time
import threading
import pyttsx3
import winsound  # Native to Windows; produces direct frequency beeps

# ==========================================
# THREADED AUDIO DISPATCHER
# ==========================================
class SoundAlertManager:
    def __init__(self):
        self.is_speaking = False
        self.last_alert_time = 0
        self.cooldown_sec = 4.0  # Prevents overlapping voice spam

    def _speak_worker(self, text):
        """Worker function running in a separate thread."""
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 165)    # Speaking speed
            engine.setProperty("volume", 1.0)  # Volume (0.0 to 1.0)
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"Voice engine error: {e}")
        finally:
            self.is_speaking = False

    def trigger_voice_alert(self, message):
        """Triggers voice alert asynchronously without freezing video."""
        curr_time = time.time()
        if not self.is_speaking and (curr_time - self.last_alert_time >= self.cooldown_sec):
            self.is_speaking = True
            self.last_alert_time = curr_time
            # Start background thread
            thread = threading.Thread(target=self._speak_worker, args=(message,), daemon=True)
            thread.start()

    def trigger_siren_pulse(self):
        """Triggers a sharp hardware siren beep in the background."""
        def _beep():
            for _ in range(3):
                winsound.Beep(2500, 150)  # 2500 Hz frequency for 150ms
                time.sleep(0.05)
        threading.Thread(target=_beep, daemon=True).start()

# Initialize Audio Engine
audio_manager = SoundAlertManager()

# ==========================================
# INTERACTIVE DEMO LOOP
# ==========================================
camera = cv2.VideoCapture(0)

print("=" * 60)
print("  SAFESIGHT THREADED AUDIO ALERT SYSTEM")
print("=" * 60)
print("  Press '1' -> Trigger Intrusion Voice Warning")
print("  Press '2' -> Trigger Camera Tampering Siren Pulse")
print("  Press '3' -> Trigger Drop & Run Luggage Voice Alert")
print("  Press 'q' -> Exit")
print("=" * 60)

while True:
    success, frame = camera.read()
    if not success:
        break

    # HUD Interface
    cv2.rectangle(frame, (10, 10), (450, 110), (15, 15, 15), -1)
    cv2.putText(frame, "SAFESIGHT AUDIO SYSTEM ACTIVE", (20, 32),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(frame, "Press 1: Intrusion Voice | Press 2: Tamper Siren", (20, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
    cv2.putText(frame, "Press 3: Luggage Alert  | Press Q: Quit", (20, 82),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)

    cv2.imshow("SafeSight - Audio Dispatch Diagnostics", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break
    elif key == ord('1'):
        print("[AUDIO] Speaking: Intrusion Alert...")
        audio_manager.trigger_voice_alert("Warning! Restricted perimeter breached. Security dispatched.")
    elif key == ord('2'):
        print("[AUDIO] Sounding Tamper Siren...")
        audio_manager.trigger_siren_pulse()
    elif key == ord('3'):
        print("[AUDIO] Speaking: Luggage Warning...")
        audio_manager.trigger_voice_alert("Security alert. Unattended baggage detected in active zone.")

camera.release()
cv2.destroyAllWindows()