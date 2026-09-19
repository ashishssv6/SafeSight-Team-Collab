import os
import cv2
import time
import shutil
import numpy as np

FACES_DIR = "known_faces"
os.makedirs(FACES_DIR, exist_ok=True)

class RobustFaceSecurityEngine:
    def __init__(self):
        self.frontal_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
        self.enrolled_profiles = {}
        self.load_enrolled_faces()

    def preprocess_face(self, face_gray, size=(110, 110)):
        """Normalizes scale and eliminates shadows using histogram equalization."""
        resized = cv2.resize(face_gray, size)
        return cv2.equalizeHist(resized)

    def detect_all_face_angles(self, gray_frame):
        """Detects frontal, right-profile, and mirrored left-profile faces."""
        h_frame, w_frame = gray_frame.shape
        detected_boxes = []

        # Frontal
        for box in self.frontal_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=4, minSize=(45, 45)):
            detected_boxes.append(list(box))

        # Right Profile
        for box in self.profile_cascade.detectMultiScale(gray_frame, scaleFactor=1.12, minNeighbors=3, minSize=(45, 45)):
            detected_boxes.append(list(box))

        # Left Profile (Horizontal Mirror Scan)
        flipped_gray = cv2.flip(gray_frame, 1)
        for (fx, fy, fw, fh) in self.profile_cascade.detectMultiScale(flipped_gray, scaleFactor=1.12, minNeighbors=3, minSize=(45, 45)):
            detected_boxes.append([w_frame - (fx + fw), fy, fw, fh])

        if not detected_boxes:
            return []

        rects, _ = cv2.groupRectangles([[x, y, w, h] for x, y, w, h in detected_boxes], groupThreshold=1, eps=0.35)
        return rects if len(rects) > 0 else detected_boxes[:2]

    def load_enrolled_faces(self):
        """Loads all multi-angle template galleries from disk."""
        self.enrolled_profiles.clear()
        if not os.path.exists(FACES_DIR):
            return

        for folder in os.listdir(FACES_DIR):
            folder_path = os.path.join(FACES_DIR, folder)
            if os.path.isdir(folder_path):
                parts = folder.split("_", 1)
                role = parts[0].upper() if len(parts) > 1 else "UNKNOWN"
                name = parts[1] if len(parts) > 1 else parts[0]
                
                templates = []
                for img_name in os.listdir(folder_path):
                    img_file = os.path.join(folder_path, img_name)
                    img = cv2.imread(img_file, cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        templates.append(self.preprocess_face(img))
                
                if templates:
                    self.enrolled_profiles[name] = {"role": role, "templates": templates}
        print(f"[FACE ENGINE] Loaded {len(self.enrolled_profiles)} active face profiles.")

    def clear_all_profiles(self):
        """Wipes the database clean."""
        if os.path.exists(FACES_DIR):
            shutil.rmtree(FACES_DIR)
            os.makedirs(FACES_DIR, exist_ok=True)
        self.enrolled_profiles.clear()
        print("[FACE ENGINE] Database wiped clean. All face profiles removed.")

    def match_face(self, face_gray_crop):
        """Matches face against ensemble angle templates."""
        if not self.enrolled_profiles:
            return "Visitor", "VISITOR", 0.0

        normalized_target = self.preprocess_face(face_gray_crop)
        best_name = "Visitor"
        best_role = "VISITOR"
        highest_score = -1.0

        for name, data in self.enrolled_profiles.items():
            for template in data["templates"]:
                res = cv2.matchTemplate(normalized_target, template, cv2.TM_CCOEFF_NORMED)
                score = float(res[0][0])
                if score > highest_score:
                    highest_score = score
                    best_name = name
                    best_role = data["role"]

        if highest_score >= 0.38:
            return best_name, best_role, highest_score
        return "Visitor", "VISITOR", highest_score

    def analyze_frame(self, frame):
        """Scans frame and returns bounding boxes, roles, and match confidence."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.detect_all_face_angles(gray)
        
        detections = []
        for (x, y, w, h) in faces:
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(frame.shape[1], x + w), min(frame.shape[0], y + h)
            if (x2 - x1) < 25 or (y2 - y1) < 25:
                continue
            face_crop = gray[y1:y2, x1:x2]
            name, role, score = self.match_face(face_crop)
            detections.append({
                "box": (x1, y1, x2 - x1, y2 - y1),
                "name": name,
                "role": role,
                "confidence": score
            })
        return detections


# ==========================================
# NON-BLOCKING INTERACTIVE HARNESS
# ==========================================
if __name__ == "__main__":
    engine = RobustFaceSecurityEngine()
    camera = cv2.VideoCapture(0)

    # State Machine Variables for Enrollment
    is_enrolling = False
    enroll_role = "VIP"
    enroll_name = "Ashish"
    enroll_target_samples = 12
    samples_captured = 0
    last_sample_time = 0
    enroll_folder = ""

    print("=" * 65)
    print("  SAFESIGHT ENROLLMENT CONSOLE")
    print("=" * 65)
    print("  [V] -> Enroll as VIP (Authorized Officer)")
    print("  [B] -> Enroll as BLACKLIST (Wanted Suspect)")
    print("  [C] -> Clear ALL profiles (Fresh Reset)")
    print("  [Q] -> Exit")
    print("=" * 65)

    while True:
        success, frame = camera.read()
        if not success:
            break

        curr_time = time.time()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ----------------------------------------------------
        # 1. ENROLLMENT STATE MACHINE (NON-BLOCKING)
        # ----------------------------------------------------
        if is_enrolling:
            faces = engine.detect_all_face_angles(gray)
            cv2.rectangle(frame, (10, 10), (560, 85), (20, 20, 20), -1)
            cv2.putText(frame, f"ENROLLING {enroll_role}: {enroll_name.upper()}", (20, 35),
                        cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 255, 255), 1)
            cv2.putText(frame, f"Captured: {samples_captured}/{enroll_target_samples} | Rotate head slightly...", (20, 62),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

            if len(faces) > 0:
                x, y, w, h = faces[0]
                x1, y1 = max(0, x), max(0, y)
                x2, y2 = min(frame.shape[1], x + w), min(frame.shape[0], y + h)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Capture sample every 160ms
                if curr_time - last_sample_time > 0.16:
                    crop = gray[y1:y2, x1:x2]
                    if crop.size > 0:
                        sample_path = os.path.join(enroll_folder, f"sample_{samples_captured + 1}.jpg")
                        cv2.imwrite(sample_path, crop)
                        samples_captured += 1
                        last_sample_time = curr_time

                if samples_captured >= enroll_target_samples:
                    is_enrolling = False
                    engine.load_enrolled_faces()
                    print(f"\n[ENROLLMENT SUCCESS] Completed {enroll_role} enrollment for {enroll_name}!")

        # ----------------------------------------------------
        # 2. ACTIVE RECOGNITION MODE
        # ----------------------------------------------------
        else:
            results = engine.analyze_frame(frame)
            for item in results:
                x, y, w, h = item["box"]
                role = item["role"]
                name = item["name"]
                score = item["confidence"]

                if role == "BLACKLIST":
                    color = (0, 0, 255)
                    badge = f"🚨 BLACKLIST: {name} ({score:.2f})"
                elif role == "VIP":
                    color = (0, 255, 0)
                    badge = f"🛡️ VIP: {name} ({score:.2f})"
                else:
                    color = (255, 200, 0)
                    badge = f"VISITOR ({score:.2f})"

                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.rectangle(frame, (x, max(0, y - 26)), (x + max(w, 200), y), color, -1)
                cv2.putText(frame, badge, (x + 4, max(14, y - 7)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)

            # Control Banner
            cv2.rectangle(frame, (10, 10), (510, 75), (15, 15, 15), -1)
            cv2.putText(frame, "SAFESIGHT RECOGNITION CONSOLE", (20, 32),
                        cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, "Press 'v': VIP | 'b': Blacklist | 'c': Clear | 'q': Quit", (20, 56),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)

        cv2.imshow("SafeSight - Facial Intelligence", frame)
        raw_key = cv2.waitKey(1) & 0xFF

        # Case-Insensitive Key Bindings
        if raw_key in [ord('q'), ord('Q')]:
            break
        elif raw_key in [ord('v'), ord('V')] and not is_enrolling:
            enroll_role = "VIP"
            enroll_name = "Ashish"
            enroll_folder = os.path.join(FACES_DIR, f"{enroll_role}_{enroll_name}")
            os.makedirs(enroll_folder, exist_ok=True)
            samples_captured = 0
            is_enrolling = True
            print(f"\n[ENROLLING] Starting VIP capture for {enroll_name}. Slowly turn head left & right...")
        elif raw_key in [ord('b'), ord('B')] and not is_enrolling:
            enroll_role = "BLACKLIST"
            enroll_name = "Suspect_01"
            enroll_folder = os.path.join(FACES_DIR, f"{enroll_role}_{enroll_name}")
            os.makedirs(enroll_folder, exist_ok=True)
            samples_captured = 0
            is_enrolling = True
            print(f"\n[ENROLLING] Starting BLACKLIST capture for {enroll_name}. Slowly turn head left & right...")
        elif raw_key in [ord('c'), ord('C')] and not is_enrolling:
            engine.clear_all_profiles()

    camera.release()
    cv2.destroyAllWindows()