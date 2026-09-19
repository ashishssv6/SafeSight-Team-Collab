import os
import cv2
import math
import time
import shutil
import sqlite3
import threading
from collections import deque
import pyttsx3
import winsound
import numpy as np
from datetime import datetime
from ultralytics import YOLO

# ==========================================
# 1. CONFIGURATION & DIRECTORIES
# ==========================================
SNAPSHOT_DIR = "alerts_snapshots"
VIDEO_DIR = "alerts_videos"
FACES_DIR = "known_faces"
DB_PATH = "safesight.db"

os.makedirs(SNAPSHOT_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(FACES_DIR, exist_ok=True)

# Behavior & Threat Thresholds (Tuned for Indoor Rooms)
NORMALIZED_SPEED_THRESH = 0.65   # Speed threshold normalized by body height
SPRINT_DEBOUNCE_FRAMES = 2       # Consecutive frames required to trigger sprint alert
BAG_ABANDON_DIST_PX = 180        # Pixel distance from person to consider bag separated
BAG_ABANDON_TIME_SEC = 3.5       # Seconds left alone before unattended alarm
LOITERING_DURATION_SEC = 6.0     # Time inside restricted zone before loitering alarm
CROWD_THRESHOLD = 3              # Number of people for crowd alarm
CROWD_DURATION_SEC = 5.0
TAMPER_DURATION_SEC = 1.8
ROLLING_BUFFER_FRAMES = 90       # 3 seconds buffer at 30 FPS

# Target COCO Classes: person (0), backpack (24), handbag (26), suitcase (28)
TARGET_CLASSES = [0, 24, 26, 28]

db_lock = threading.Lock()

# ==========================================
# 2. DATABASE UTILITIES
# ==========================================
def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                track_id INTEGER,
                threat_score INTEGER NOT NULL,
                threat_level TEXT NOT NULL,
                details TEXT,
                snapshot_path TEXT,
                video_path TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                val TEXT NOT NULL
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO system_config (key, val) VALUES ('face_detection_enabled', '1')")
        conn.commit()
        conn.close()

def get_config_val(key, default="1"):
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            cur = conn.cursor()
            cur.execute("SELECT val FROM system_config WHERE key = ?", (key,))
            row = cur.fetchone()
            conn.close()
            return row[0] if row else default
    except Exception:
        return default

def set_config_val(key, val):
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO system_config (key, val) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET val=excluded.val
            """, (key, str(val)))
            conn.commit()
            conn.close()
    except Exception:
        pass

def log_event_to_db(event_type, track_id, threat_score, threat_level, details, snapshot_path=None, video_path=None):
    def _async_log():
        try:
            with db_lock:
                conn = sqlite3.connect(DB_PATH, timeout=8)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO security_events (event_type, track_id, threat_score, threat_level, details, snapshot_path, video_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (event_type, track_id, threat_score, threat_level, details, snapshot_path, video_path))
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"[DB ERROR] Log write failed: {e}")
    threading.Thread(target=_async_log, daemon=True).start()

init_db()

# ==========================================
# 3. FAULT-TOLERANT VIDEO CAPTURE
# ==========================================
class ResilientCapture:
    def __init__(self, src=0):
        self.src = src
        self.cap = cv2.VideoCapture(self.src)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    def read(self):
        if not self.cap.isOpened():
            self._reconnect()
        ret, frame = self.cap.read()
        if not ret:
            self._reconnect()
            ret, frame = self.cap.read()
        return ret, frame

    def _reconnect(self):
        self.cap.release()
        time.sleep(0.5)
        self.cap = cv2.VideoCapture(self.src)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    def release(self):
        self.cap.release()

# ==========================================
# 4. THREADED AUDIO & LOW-MEMORY RECORDER
# ==========================================
class SoundAlertManager:
    def __init__(self):
        self.is_speaking = False
        self.last_speech_time = 0

    def _speak_worker(self, text):
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass
        finally:
            self.is_speaking = False

    def speak(self, text, cooldown=4.0):
        curr = time.time()
        if not self.is_speaking and (curr - self.last_speech_time >= cooldown):
            self.is_speaking = True
            self.last_speech_time = curr
            threading.Thread(target=self._speak_worker, args=(text,), daemon=True).start()

    def siren_pulse(self):
        def _beep():
            for _ in range(3):
                winsound.Beep(2600, 120)
                time.sleep(0.04)
        threading.Thread(target=_beep, daemon=True).start()

class RollingVideoRecorder:
    def __init__(self, max_frames=ROLLING_BUFFER_FRAMES):
        self.frame_buffer = deque(maxlen=max_frames)

    def push_frame(self, frame):
        # Store half-resolution to keep RAM usage minimal
        small = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_NEAREST)
        self.frame_buffer.append(small)

    def _save_video_worker(self, frames_list, output_path, fps=24.0):
        if not frames_list:
            return
        try:
            h, w, _ = frames_list[0].shape
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))
            if not out.isOpened():
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))
            for f in frames_list:
                out.write(f)
            out.release()
            print(f"[RECORDER] Incident video clip compiled: {output_path}")
        except Exception as e:
            print(f"[RECORDER ERROR] Failed writing video: {e}")

    def capture_incident_clip_async(self, output_path):
        current_frames_snapshot = list(self.frame_buffer)
        threading.Thread(target=self._save_video_worker, args=(current_frames_snapshot, output_path), daemon=True).start()

sound_mgr = SoundAlertManager()
video_recorder = RollingVideoRecorder()

# ==========================================
# 5. FACE RECOGNITION ENGINE
# ==========================================
class FaceSecurityEngine:
    def __init__(self):
        self.frontal_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.enrolled_profiles = {}
        self.load_enrolled_faces()

    def preprocess(self, gray_face):
        resized = cv2.resize(gray_face, (100, 100))
        return cv2.equalizeHist(resized)

    def load_enrolled_faces(self):
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
                    img = cv2.imread(os.path.join(folder_path, img_name), cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        templates.append(self.preprocess(img))
                if templates:
                    self.enrolled_profiles[name] = {"role": role, "templates": templates}

    def purge_all(self):
        if os.path.exists(FACES_DIR):
            shutil.rmtree(FACES_DIR)
            os.makedirs(FACES_DIR, exist_ok=True)
        self.enrolled_profiles.clear()

    def detect_faces(self, gray_frame):
        small = cv2.resize(gray_frame, (0, 0), fx=0.5, fy=0.5)
        boxes = self.frontal_cascade.detectMultiScale(small, scaleFactor=1.15, minNeighbors=4, minSize=(30, 30))
        return [[x * 2, y * 2, w * 2, h * 2] for (x, y, w, h) in boxes]

    def match(self, gray_crop):
        if not self.enrolled_profiles:
            return "Visitor", "VISITOR", 0.0
        norm = self.preprocess(gray_crop)
        best_name, best_role, highest = "Visitor", "VISITOR", -1.0
        for name, data in self.enrolled_profiles.items():
            for tmpl in data["templates"]:
                score = float(cv2.matchTemplate(norm, tmpl, cv2.TM_CCOEFF_NORMED)[0][0])
                if score > highest:
                    highest, best_name, best_role = score, name, data["role"]
        if highest >= 0.40:
            return best_name, best_role, highest
        return "Visitor", "VISITOR", highest

    def analyze_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.detect_faces(gray)
        detections = []
        for (x, y, w, h) in faces:
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(frame.shape[1], x + w), min(frame.shape[0], y + h)
            if (x2 - x1) < 25 or (y2 - y1) < 25:
                continue
            crop = gray[y1:y2, x1:x2]
            name, role, score = self.match(crop)
            detections.append({"box": (x1, y1, x2 - x1, y2 - y1), "name": name, "role": role, "confidence": score})
        return detections

face_engine = FaceSecurityEngine()

# ==========================================
# 6. SPATIAL POSSESSION & SEPARATION ENGINE
# ==========================================
def compute_box_distance(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    x_overlap = max(0, min(ax2, bx2) - max(ax1, bx1))
    y_overlap = max(0, min(ay2, by2) - max(ay1, by1))
    if x_overlap > 0 and y_overlap > 0:
        return 0.0

    dx = max(0, max(ax1, bx1) - min(ax2, bx2))
    dy = max(0, max(ay1, by1) - min(ay2, by2))
    return math.hypot(dx, dy)

class PersistentBagTracker:
    def __init__(self):
        self.bags = {}
        self.next_bag_id = 1
        self.alerted_bags = set()

    def update(self, detected_bag_boxes, curr_time, person_boxes):
        for (x1, y1, x2, y2, cls_label) in detected_bag_boxes:
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            matched_id = None
            
            for b_id, b_data in self.bags.items():
                prev_cx, prev_cy = b_data['center']
                if math.hypot(cx - prev_cx, cy - prev_cy) < 70:
                    matched_id = b_id
                    break
            
            if matched_id is None:
                matched_id = self.next_bag_id
                self.next_bag_id += 1
                self.bags[matched_id] = {
                    'box': (x1, y1, x2, y2),
                    'center': (cx, cy),
                    'label': cls_label,
                    'first_seen': curr_time,
                    'last_seen': curr_time,
                    'separated_start': None
                }
            else:
                self.bags[matched_id]['box'] = (x1, y1, x2, y2)
                self.bags[matched_id]['center'] = (cx, cy)
                self.bags[matched_id]['last_seen'] = curr_time

        for b_id in list(self.bags.keys()):
            if curr_time - self.bags[b_id]['last_seen'] > 8.0:
                del self.bags[b_id]
                self.alerted_bags.discard(b_id)

        threat_events = []
        for b_id, b_data in self.bags.items():
            b_box = b_data['box']
            min_edge_dist = float('inf')
            
            for p_id, p_box in person_boxes.items():
                d = compute_box_distance(b_box, p_box)
                if d < min_edge_dist:
                    min_edge_dist = d

            is_held = min_edge_dist < BAG_ABANDON_DIST_PX

            if not is_held:
                if b_data['separated_start'] is None:
                    b_data['separated_start'] = curr_time
                
                unattended_duration = curr_time - b_data['separated_start']
                if unattended_duration >= BAG_ABANDON_TIME_SEC:
                    threat_events.append((b_id, b_data, unattended_duration, True, "UNATTENDED"))
                else:
                    threat_events.append((b_id, b_data, unattended_duration, False, "SEPARATING"))
            else:
                b_data['separated_start'] = None
                threat_events.append((b_id, b_data, 0.0, False, "IN HAND / CARRIED"))

        return threat_events

bag_tracker = PersistentBagTracker()

class SafeSightTracker:
    def __init__(self):
        self.positions = {}
        self.high_speed_counts = {}
        self.active_intrusions = set()
        self.zone_entry_times = {}
        self.active_loitering = set()
        self.active_running = set()

tracker_state = SafeSightTracker()

crowd_start_time = None
tamper_start_time = None
tamper_alerted = False
vision_mode = "NORMAL"
clahe_filter = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))

drawing = False
zone_start, zone_end = None, None

def draw_zone_callback(event, x, y, flags, param):
    global drawing, zone_start, zone_end
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        zone_start, zone_end = (x, y), (x, y)
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        zone_end = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        zone_end = (x, y)

# ==========================================
# 7. MAIN SURVEILLANCE LOOP
# ==========================================
def main():
    global crowd_start_time, tamper_start_time, tamper_alerted
    global zone_start, zone_end, vision_mode

    model = YOLO("yolov8n.pt")
    camera = ResilientCapture(0)

    win_name = "SafeSight Autonomous AI Sentry Matrix"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 1280, 720)
    cv2.setMouseCallback(win_name, draw_zone_callback)

    is_enrolling = False
    enroll_role = "VIP"
    enroll_name = "Ashish"
    enroll_target = 10
    samples_count = 0
    last_sample_t = 0
    enroll_dir = ""

    frame_counter = 0
    cached_face_results = []
    prev_time = time.time()

    print("=" * 65)
    print("  SAFESIGHT SURVEILLANCE MATRIX ACTIVE & SCANNING")
    print("=" * 65)

    while True:
        success, frame = camera.read()
        if not success or frame is None:
            time.sleep(0.05)
            continue

        video_recorder.push_frame(frame)
        frame_counter += 1
        curr_time = time.time()
        fps = 1.0 / max(curr_time - prev_time, 0.001)
        prev_time = curr_time

        threat_score = 0
        active_alerts = []
        is_tampered = False
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ----------------------------------------------------
        # ENROLLMENT OVERRIDE
        # ----------------------------------------------------
        if is_enrolling:
            faces = face_engine.detect_faces(gray_frame)
            cv2.rectangle(frame, (10, 10), (480, 60), (20, 20, 20), -1)
            cv2.putText(frame, f"ENROLLING {enroll_role}: {enroll_name.upper()} ({samples_count}/{enroll_target})", (20, 36),
                        cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 255, 255), 1)

            if len(faces) > 0:
                x, y, w, h = faces[0]
                x1, y1 = max(0, x), max(0, y)
                x2, y2 = min(frame.shape[1], x + w), min(frame.shape[0], y + h)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                if curr_time - last_sample_t > 0.18:
                    crop = gray_frame[y1:y2, x1:x2]
                    if crop.size > 0:
                        cv2.imwrite(os.path.join(enroll_dir, f"sample_{samples_count+1}.jpg"), crop)
                        samples_count += 1
                        last_sample_t = curr_time

                if samples_count >= enroll_target:
                    is_enrolling = False
                    face_engine.load_enrolled_faces()
                    sound_mgr.speak(f"{enroll_role} enrolled successfully.")

            cv2.imshow(win_name, frame)
            raw_k = cv2.waitKey(1) & 0xFF
            if raw_k in [ord('q'), ord('Q')]:
                break
            continue

        # --- A. LOW-MEMORY ANTI-TAMPER ENGINE ---
        # Subsample thumbnail for constant-time, low-RAM variance checks
        small_gray = cv2.resize(gray_frame, (320, 180), interpolation=cv2.INTER_NEAREST)
        hsv_small = cv2.cvtColor(cv2.resize(frame, (320, 180), interpolation=cv2.INTER_NEAREST), cv2.COLOR_BGR2HSV)
        
        mean_bright = float(np.mean(small_gray))
        std_dev = float(np.std(small_gray))
        laplacian_var = float(cv2.Laplacian(small_gray, cv2.CV_32F).var())
        mean_saturation = float(np.mean(hsv_small[:, :, 1]))

        is_blackout = mean_bright < 20.0
        is_blinded = mean_bright > 240.0
        is_low_texture = laplacian_var < 50.0 and std_dev < 20.0
        is_paper_sheet = (mean_bright > 120.0) and (mean_saturation < 35.0) and (laplacian_var < 200.0) and (std_dev < 45.0)

        if is_blackout or is_blinded or is_low_texture or is_paper_sheet:
            if tamper_start_time is None:
                tamper_start_time = curr_time
            tamper_dur = curr_time - tamper_start_time
            if tamper_dur >= TAMPER_DURATION_SEC:
                is_tampered = True
                threat_score += 100
                active_alerts.append(f"OCCLUSION ({tamper_dur:.1f}s)")
                sound_mgr.siren_pulse()
                if not tamper_alerted:
                    tamper_alerted = True
                    snap_path = f"{SNAPSHOT_DIR}/tamper_{int(curr_time)}.jpg"
                    vid_path = f"{VIDEO_DIR}/tamper_{int(curr_time)}.mp4"
                    cv2.imwrite(snap_path, frame)
                    video_recorder.capture_incident_clip_async(vid_path)
                    log_event_to_db("Hardware Camera Tampering", None, 100, "CRITICAL", f"Var: {laplacian_var:.1f}", snap_path, vid_path)
        else:
            tamper_start_time = None
            tamper_alerted = False

        # --- B. MULTI-SPECTRAL TRANSFORM ---
        if vision_mode == "THERMAL":
            render_frame = cv2.applyColorMap(gray_frame, cv2.COLORMAP_INFERNO)
        elif vision_mode == "NIGHT_VISION":
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            merged = cv2.merge((clahe_filter.apply(l), a, b))
            night_bgr = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
            night_bgr[:, :, 0] = cv2.multiply(night_bgr[:, :, 0], 0.7)
            night_bgr[:, :, 2] = cv2.multiply(night_bgr[:, :, 2], 0.7)
            night_bgr[:, :, 1] = cv2.add(night_bgr[:, :, 1], 30)
            render_frame = night_bgr
        else:
            render_frame = frame.copy()

        # --- C. FACIAL RECOGNITION (RUNS EVERY 3 FRAMES) ---
        face_scan_active = get_config_val("face_detection_enabled", "1") == "1"

        if face_scan_active:
            if frame_counter % 3 == 0:
                cached_face_results = face_engine.analyze_frame(frame)

            for item in cached_face_results:
                fx, fy, fw, fh = item["box"]
                role, name, score = item["role"], item["name"], item["confidence"]

                if role == "BLACKLIST":
                    threat_score += 65
                    f_color = (0, 0, 255)
                    active_alerts.append(f"BLACKLIST: {name}")
                    sound_mgr.speak(f"Alert! Blacklisted target {name} spotted.")
                elif role == "VIP":
                    f_color = (0, 255, 0)
                else:
                    f_color = (255, 200, 0)

                cv2.rectangle(render_frame, (fx, fy), (fx + fw, fy + fh), f_color, 2)
                cv2.rectangle(render_frame, (fx, max(0, fy - 20)), (fx + max(fw, 140), fy), f_color, -1)
                cv2.putText(render_frame, f"{name} ({role})", (fx + 4, max(12, fy - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1, cv2.LINE_AA)

        # --- D. YOLOv8 OBJECT DETECTION & SPRINT SPEED DIAGNOSTICS ---
        results = model.track(
            frame,
            persist=True,
            verbose=False,
            classes=TARGET_CLASSES,
            conf=0.20
        )
        result = results[0]

        person_count = 0
        person_boxes = {}
        detected_bags = []

        rz_x1, rz_y1, rz_x2, rz_y2 = None, None, None, None
        if zone_start and zone_end:
            rz_x1, rz_x2 = min(zone_start[0], zone_end[0]), max(zone_start[0], zone_end[0])
            rz_y1, rz_y2 = min(zone_start[1], zone_end[1]), max(zone_start[1], zone_end[1])
            cv2.rectangle(render_frame, (rz_x1, rz_y1), (rz_x2, rz_y2), (0, 0, 255), 2)
            cv2.putText(render_frame, "RESTRICTED BOUNDARY", (rz_x1 + 6, max(18, rz_y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 255), 1)

        if result.boxes is not None and len(result.boxes) > 0:
            boxes = result.boxes.xyxy.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy()
            track_ids = result.boxes.id.cpu().numpy() if result.boxes.id is not None else [None] * len(boxes)

            for box, cls_id, t_id in zip(boxes, classes, track_ids):
                cls_name = model.names[int(cls_id)]
                x1, y1, x2, y2 = map(int, box)
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                if cls_name in ["backpack", "handbag", "suitcase"]:
                    detected_bags.append((x1, y1, x2, y2, cls_name.upper()))
                    continue

                if cls_name == "person":
                    person_count += 1
                    track_id = int(t_id) if t_id is not None else person_count
                    person_boxes[track_id] = (x1, y1, x2, y2)
                    h = max(y2 - y1, 1)

                    norm_speed = 0.0
                    if track_id in tracker_state.positions:
                        old_cx, old_cy, old_h, old_t = tracker_state.positions[track_id]
                        dt = max(curr_time - old_t, 0.001)
                        norm_speed = (math.hypot(cx - old_cx, cy - old_cy) / h) / dt

                    tracker_state.positions[track_id] = (cx, cy, h, curr_time)

                    # Debouncing Speed Logic
                    if norm_speed > NORMALIZED_SPEED_THRESH:
                        tracker_state.high_speed_counts[track_id] = tracker_state.high_speed_counts.get(track_id, 0) + 1
                    else:
                        tracker_state.high_speed_counts[track_id] = max(0, tracker_state.high_speed_counts.get(track_id, 0) - 1)

                    is_running = tracker_state.high_speed_counts[track_id] >= SPRINT_DEBOUNCE_FRAMES

                    # Zone Breach Check
                    inside_zone = False
                    if rz_x1 is not None and rz_y1 is not None:
                        centroid_in = (rz_x1 <= cx <= rz_x2) and (rz_y1 <= cy <= rz_y2)
                        overlap_x = max(0, min(x2, rz_x2) - max(x1, rz_x1))
                        overlap_y = max(0, min(y2, rz_y2) - max(y1, rz_y1))
                        overlap_area = overlap_x * overlap_y
                        box_area = max((x2 - x1) * (y2 - y1), 1)
                        inside_zone = centroid_in or (overlap_area / box_area > 0.20)

                    p_color = (0, 255, 0)
                    if inside_zone:
                        threat_score += 45
                        p_color = (0, 0, 255)
                        active_alerts.append(f"Zone Breach: ID {track_id}")

                        if track_id not in tracker_state.active_intrusions:
                            tracker_state.active_intrusions.add(track_id)
                            tracker_state.zone_entry_times[track_id] = curr_time
                            sound_mgr.speak("Warning! Restricted perimeter breached.")
                            snap_path = f"{SNAPSHOT_DIR}/intrusion_{track_id}_{int(curr_time)}.jpg"
                            vid_path = f"{VIDEO_DIR}/intrusion_{track_id}_{int(curr_time)}.mp4"
                            cv2.imwrite(snap_path, frame[max(0, y1-10):min(frame.shape[0], y2+10), max(0, x1-10):min(frame.shape[1], x2+10)])
                            video_recorder.capture_incident_clip_async(vid_path)
                            log_event_to_db("Restricted Zone Intrusion", track_id, 75, "HIGH", f"Centroid: ({cx},{cy})", snap_path, vid_path)

                        in_zone_dur = curr_time - tracker_state.zone_entry_times.get(track_id, curr_time)
                        if in_zone_dur >= LOITERING_DURATION_SEC:
                            threat_score += 30
                            active_alerts.append(f"Loiter: ID {track_id} ({in_zone_dur:.0f}s)")
                            if track_id not in tracker_state.active_loitering:
                                tracker_state.active_loitering.add(track_id)
                                sound_mgr.speak("Security notice. Loitering detected.")
                    else:
                        tracker_state.active_intrusions.discard(track_id)
                        tracker_state.active_loitering.discard(track_id)
                        tracker_state.zone_entry_times.pop(track_id, None)

                    if is_running:
                        threat_score += 25
                        active_alerts.append(f"Sprint: ID {track_id}")
                        tracker_state.active_running.add(track_id)
                        p_color = (0, 140, 255)
                    else:
                        tracker_state.active_running.discard(track_id)

                    cv2.rectangle(render_frame, (x1, y1), (x2, y2), p_color, 2)
                    cv2.circle(render_frame, (cx, cy), 4, (0, 255, 255), -1)

                    speed_label = f"ID:{track_id} | Spd:{norm_speed:.2f} | R:{tracker_state.high_speed_counts.get(track_id, 0)}/{SPRINT_DEBOUNCE_FRAMES}"
                    cv2.putText(render_frame, speed_label, (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.40, p_color, 1)

        # --- E. CARRIED VS UNATTENDED LUGGAGE ---
        bag_statuses = bag_tracker.update(detected_bags, curr_time, person_boxes)

        for b_id, b_data, un_dur, is_threat, status_desc in bag_statuses:
            bx1, by1, bx2, by2 = b_data['box']
            label = b_data['label']

            if is_threat:
                threat_score += 55
                active_alerts.append(f"UNATTENDED {label} #{b_id} ({un_dur:.0f}s)")
                bag_color = (0, 0, 255)

                if b_id not in bag_tracker.alerted_bags:
                    bag_tracker.alerted_bags.add(b_id)
                    sound_mgr.speak(f"Security alert. Unattended {label.lower()} detected.")
                    snap_path = f"{SNAPSHOT_DIR}/abandoned_{b_id}_{int(curr_time)}.jpg"
                    vid_path = f"{VIDEO_DIR}/abandoned_{b_id}_{int(curr_time)}.mp4"
                    cv2.imwrite(snap_path, frame)
                    video_recorder.capture_incident_clip_async(vid_path)
                    log_event_to_db("Unattended Baggage Anomaly", b_id, 90, "CRITICAL", f"{label} left unattended for {un_dur:.1f}s", snap_path, vid_path)
            elif status_desc == "SEPARATING":
                bag_color = (0, 165, 255)
            else:
                bag_color = (0, 255, 0)

            cv2.rectangle(render_frame, (bx1, by1), (bx2, by2), bag_color, 2)
            cv2.putText(render_frame, f"{label} [{status_desc}]", (bx1, max(14, by1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, bag_color, 1)

        # --- F. CROWD GATHERING ---
        if person_count >= CROWD_THRESHOLD:
            if crowd_start_time is None:
                crowd_start_time = curr_time
            crowd_dur = curr_time - crowd_start_time
            if crowd_dur >= CROWD_DURATION_SEC:
                threat_score += 35
                active_alerts.append(f"Crowd: {person_count} ({crowd_dur:.0f}s)")
        else:
            crowd_start_time = None

        # --- G. COMPACT HUD STATUS BAR ---
        threat_score = min(threat_score, 100)
        if threat_score >= 80:
            threat_level, hud_color = "CRITICAL", (0, 0, 255)
        elif threat_score >= 50:
            threat_level, hud_color = "HIGH", (0, 140, 255)
        elif threat_score >= 25:
            threat_level, hud_color = "CAUTION", (0, 215, 255)
        else:
            threat_level, hud_color = "NORMAL", (0, 200, 0)

        overlay_ui = render_frame.copy()
        cv2.rectangle(overlay_ui, (12, 12), (380, 68), (15, 15, 15), -1)
        cv2.addWeighted(overlay_ui, 0.75, render_frame, 0.25, 0, render_frame)
        cv2.rectangle(render_frame, (12, 12), (380, 68), (70, 70, 70), 1)

        f_state = "ON" if face_scan_active else "OFF"
        cv2.putText(render_frame, f"SAFESIGHT [{vision_mode}] | FPS: {fps:.0f} | Face: {f_state}", (22, 32),
                    cv2.FONT_HERSHEY_DUPLEX, 0.42, (255, 255, 255), 1)
        cv2.putText(render_frame, f"STATUS: {threat_level} ({threat_score}/100)", (22, 54),
                    cv2.FONT_HERSHEY_DUPLEX, 0.52, hud_color, 2)

        if active_alerts:
            cv2.putText(render_frame, f"! {active_alerts[0]}", (200, 54),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 180, 255), 1)

        if is_tampered:
            cv2.rectangle(render_frame, (0, 0), (render_frame.shape[1], render_frame.shape[0]), (0, 0, 255), 6)

        cv2.imshow(win_name, render_frame)
        raw_key = cv2.waitKey(1) & 0xFF

        if raw_key in [ord('q'), ord('Q')]:
            break
        elif raw_key in [ord('v'), ord('V')] and not is_enrolling:
            enroll_role = "VIP"
            enroll_name = "Ashish"
            enroll_dir = os.path.join(FACES_DIR, f"{enroll_role}_{enroll_name}")
            os.makedirs(enroll_dir, exist_ok=True)
            samples_count = 0
            is_enrolling = True
        elif raw_key in [ord('b'), ord('B')] and not is_enrolling:
            enroll_role = "BLACKLIST"
            enroll_name = "Suspect"
            enroll_dir = os.path.join(FACES_DIR, f"{enroll_role}_{enroll_name}")
            os.makedirs(enroll_dir, exist_ok=True)
            samples_count = 0
            is_enrolling = True
        elif raw_key in [ord('x'), ord('X')]:
            face_engine.purge_all()
        elif raw_key in [ord('c'), ord('C')]:
            zone_start, zone_end = None, None
        elif raw_key in [ord('f'), ord('F')]:
            new_state = "0" if face_scan_active else "1"
            set_config_val("face_detection_enabled", new_state)
        elif raw_key in [ord('t'), ord('T')]:
            vision_mode = "THERMAL"
        elif raw_key in [ord('n'), ord('N')]:
            vision_mode = "NIGHT_VISION"
        elif raw_key in [ord('o'), ord('O')]:
            vision_mode = "NORMAL"

    camera.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()