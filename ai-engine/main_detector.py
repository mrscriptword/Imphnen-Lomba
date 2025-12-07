import cv2
import time
import os
import face_recognition
import numpy as np
from ultralytics import YOLO
import math
import pyttsx3 
import threading 
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
import queue 

# ==========================================
# 1. KONFIGURASI SENSITIF (ALL-IN-ONE TUNING)
# ==========================================
load_dotenv()

# YOLO Class IDs
CLASS_ID_PERSON = 0
CLASS_ID_CUP = 41
CLASS_ID_PHONE = 67
TARGET_CLASSES = [CLASS_ID_PERSON, CLASS_ID_CUP, CLASS_ID_PHONE]

# Koordinat Zona (Sesuaikan dengan Kamera)
ZONE_COFFEE_MAKER = [100, 100, 400, 400] 
DOOR_LINE_X_POSITION = 300
DOOR_LINE_TOLERANCE = 30 

# --- TUNING LEVEL: SANGAT PEKA ---
YOLO_CONFIDENCE = 0.35              # Rendah: Agar objek kecil/gelap terlihat
FACE_REC_TOLERANCE = 0.6            # Tinggi: Agar wajah miring/buram tetap dikenali sbg Pegawai
VERIFICATION_GRACE_PERIOD = 10      # Cepat: Cuma butuh 0.5 detik untuk verifikasi identitas
INTERVAL_FACE_RECOGNITION = 3       # Sering: Cek wajah setiap 3 frame
INTERVAL_UPLOAD_STATS_SEC = 5

# Waktu (Detik) - DIPERCEPAT
THRESHOLD_PHONE_USAGE_SEC = 3       # 3 Detik main HP langsung warning
THRESHOLD_COFFEE_BREW_SEC = 4       # 4 Detik di zona kopi dianggap kerja
COOLDOWN_BETWEEN_CUPS_SEC = 10      

# Tampilan
FONT_STYLE = cv2.FONT_HERSHEY_SIMPLEX
COLOR_RED = (0, 0, 255)
COLOR_GREEN = (0, 255, 0)
COLOR_YELLOW = (0, 255, 255)
COLOR_ORANGE = (0, 165, 255)

# ==========================================
# 2. DATABASE WORKER
# ==========================================
db_task_queue = queue.Queue()

def database_worker_thread():
    try:
        mongo_uri = os.getenv("MONGO_URI")
        client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
        db_instance = client["I_MBG"]
        col_employees = db_instance["employee_performance"]
        col_system_logs = db_instance["system_logs"]
        col_visitor_logs = db_instance["visitor_logs"]
        print("✅ [DB] Database Connected Successfully")
    except Exception as e:
        print(f"❌ [DB] Connection Error: {e}")
        return

    while True:
        try:
            task = db_task_queue.get()
            if task is None: break 
            action_type, payload = task
            
            if action_type == "log_event":
                col_system_logs.insert_one(payload)
                print(f"☁️ [LOG] {payload['event']}") 
            elif action_type == "update_employee":
                col_employees.update_one({"name": payload['name']},
                    {"$inc": {"cups": payload['cups_added']}, "$set": {"last_seen": payload['ts'], "status": payload['status']}},
                    upsert=True)
            elif action_type == "visitor_stats":
                col_visitor_logs.insert_one(payload)
            db_task_queue.task_done()
        except Exception as e:
            print(f"⚠️ [DB] Upload Failed: {e}")

threading.Thread(target=database_worker_thread, daemon=True).start()

def queue_log_event(event_name, detail_text):
    db_task_queue.put(("log_event", {"timestamp": datetime.now(), "event": event_name, "detail": detail_text}))

def queue_employee_update(name, cups=0, status="Active"):
    db_task_queue.put(("update_employee", {"name": name, "cups_added": cups, "ts": datetime.now(), "status": status}))

def queue_visitor_stats(total_in, current_occupancy):
    db_task_queue.put(("visitor_stats", {"timestamp": datetime.now(), "camera_id": "CAM_MAIN", "total_in": total_in, "total_out": 0, "current_occupancy": current_occupancy}))

# ==========================================
# 3. AI ENGINE SETUP
# ==========================================
def text_to_speech(text):
    def run_speech():
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.say(text)
            engine.runAndWait()
        except: pass
    threading.Thread(target=run_speech).start()

print("⏳ Loading Face Data...")
known_face_encodings = []
known_face_names = []
employee_daily_score = {} 
PATH_FACE_DATA = "data_wajah"

if not os.path.exists(PATH_FACE_DATA): os.makedirs(PATH_FACE_DATA)

for filename in os.listdir(PATH_FACE_DATA):
    if filename.endswith(('.jpg', '.png', '.jpeg')):
        try:
            image_path = os.path.join(PATH_FACE_DATA, filename)
            loaded_image = face_recognition.load_image_file(image_path)
            encoding = face_recognition.face_encodings(loaded_image)[0]
            name = os.path.splitext(filename)[0].upper()
            known_face_encodings.append(encoding)
            known_face_names.append(name)
            employee_daily_score[name] = 0
            print(f"   👤 Loaded: {name}")
        except: pass

print("⏳ Loading YOLOv8...")
model = YOLO('yolov8n.pt') 

# ==========================================
# 4. LOGIC VARIABLES
# ==========================================
visitor_count_total = 0 
unique_visitor_ids = set()
visitor_face_memory = []
tracker_id_to_name = {} 
tracker_id_to_face_enc = {} 
track_id_age = {} 

phone_usage_timers = {} 
phone_grace_period = {} 
phone_violation_reported = set() 

cup_cooldown_timers = {} 
cup_in_zone_status = {}
cup_entry_timestamps = {}
cup_last_seen_frame = {}
cup_maker_assignment = {} 
cup_last_coordinates = {}      
lost_cups_buffer = [] 

frame_counter = 0
last_stats_upload_time = time.time()

# --- GEOMETRIC HELPERS (REVISI TOTAL: HIGH SENSITIVITY) ---
def get_overlap_ratio(box_small, box_large):
    """Menghitung overlap untuk HP/Gelas. Peka jika > 10% area nempel."""
    xA = max(box_small[0], box_large[0])
    yA = max(box_small[1], box_large[1])
    xB = min(box_small[2], box_large[2])
    yB = min(box_small[3], box_large[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxSmallArea = (box_small[2] - box_small[0]) * (box_small[3] - box_small[1])
    if boxSmallArea == 0: return 0
    return interArea / float(boxSmallArea)

def is_face_aligned_with_body(face_box, body_box):
    """
    Logika Super Peka: Menggunakan Alignment Titik Tengah.
    Wajah boleh sedikit di luar kotak badan, asalkan posisinya di 'atas' badan.
    Ini mengatasi masalah bounding box YOLO yang kadang tidak mencakup kepala full.
    """
    fx1, fy1, fx2, fy2 = face_box
    bx1, by1, bx2, by2 = body_box
    
    face_cx = (fx1 + fx2) / 2
    face_cy = (fy1 + fy2) / 2
    body_cx = (bx1 + bx2) / 2
    
    # Toleransi X: Wajah boleh melenceng kiri/kanan 80px dari tengah badan
    x_aligned = abs(face_cx - body_cx) < (bx2 - bx1) * 0.8 
    
    # Toleransi Y: Wajah harus di area atas badan (atau sedikit floating di atasnya)
    # Kita ambil 1/3 bagian atas badan sebagai area wajar kepala
    body_upper_limit = by1 - (by2 - by1) * 0.3 
    body_chest_line = by1 + (by2 - by1) * 0.5
    y_aligned = body_upper_limit < face_cy < body_chest_line
    
    return x_aligned and y_aligned

def get_closest_person(target_center, people_list, max_distance=600): # Jarak diperluas 600px
    if not people_list: return None
    closest_identity = None
    min_dist = float('inf')
    tx, ty = target_center
    for person in people_list:
        px, py = person['center']
        dist = math.hypot(tx - px, ty - py)
        if dist < min_dist:
            min_dist = dist
            closest_identity = person['identity']
    if min_dist < max_distance: return closest_identity
    return None

# ==========================================
# 5. MAIN EXECUTION LOOP
# ==========================================
camera_index = int(os.getenv('CAMERA_INDEX', 0))
video_capture = cv2.VideoCapture(camera_index)
video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print("🚀 System Online (FULL SENSITIVE MODE).")
queue_log_event("SYSTEM", "AI Engine Started - Full Sensitive")

while True:
    is_frame_valid, frame = video_capture.read()
    if not is_frame_valid: break
    frame_counter += 1
    current_timestamp = time.time()
    height, width, _ = frame.shape

    # ----------------------------------------
    # A. FACE RECOGNITION (TOLERANT MODE)
    # ----------------------------------------
    detected_faces_batch = [] 
    if frame_counter % INTERVAL_FACE_RECOGNITION == 0:
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = np.ascontiguousarray(small_frame[:, :, ::-1])
        face_locations = face_recognition.face_locations(rgb_small_frame)
        
        if len(face_locations) > 0:
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
            for loc, encoding in zip(face_locations, face_encodings):
                top, right, bottom, left = loc
                scaled_loc = (top*4, right*4, bottom*4, left*4)
                identity_name = "UNKNOWN"
                
                # Cek Pegawai dengan Toleransi Tinggi (0.6)
                if len(known_face_encodings) > 0:
                    matches = face_recognition.compare_faces(known_face_encodings, encoding, tolerance=FACE_REC_TOLERANCE)
                    face_distances = face_recognition.face_distance(known_face_encodings, encoding)
                    if len(face_distances) > 0:
                        best_match_index = np.argmin(face_distances)
                        if matches[best_match_index]:
                            identity_name = known_face_names[best_match_index]
                
                detected_faces_batch.append((scaled_loc, identity_name, encoding))

    # ----------------------------------------
    # B. YOLO TRACKING
    # ----------------------------------------
    results = model.track(frame, classes=TARGET_CLASSES, persist=True, verbose=False, conf=YOLO_CONFIDENCE, tracker="bytetrack.yaml")
    
    cv2.rectangle(frame, (ZONE_COFFEE_MAKER[0], ZONE_COFFEE_MAKER[1]), (ZONE_COFFEE_MAKER[2], ZONE_COFFEE_MAKER[3]), COLOR_RED, 2)
    cv2.line(frame, (DOOR_LINE_X_POSITION, 0), (DOOR_LINE_X_POSITION, height), COLOR_YELLOW, 2)

    active_cup_track_ids = set()
    list_people_on_screen = [] 
    list_phones_on_screen = []

    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
        class_ids = results[0].boxes.cls.cpu().numpy().astype(int)
        tracking_ids = results[0].boxes.id.cpu().numpy().astype(int)

        # 1. Kumpulkan HP
        for box, cls_id in zip(boxes, class_ids):
            if cls_id == CLASS_ID_PHONE:
                list_phones_on_screen.append(box)
                cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), COLOR_RED, 2)

        # 2. Proses Manusia (Identity Matching yang Lebih Pintar)
        for box, cls_id, track_id in zip(boxes, class_ids, tracking_ids):
            if cls_id == CLASS_ID_PERSON:
                x1, y1, x2, y2 = box
                center_x, center_y = int((x1+x2)/2), int((y1+y2)/2)
                
                current_age = track_id_age.get(track_id, 0) + 1
                track_id_age[track_id] = current_age

                # Update Identitas
                if frame_counter % INTERVAL_FACE_RECOGNITION == 0:
                    matched_name = None
                    matched_encoding = None
                    for face_loc, name, enc in detected_faces_batch:
                        # GUNAKAN LOGIKA ALIGNMENT BARU
                        if is_face_aligned_with_body(face_loc, box):
                            matched_name = name
                            matched_encoding = enc
                            break
                    
                    if matched_name and matched_name != "UNKNOWN": 
                        tracker_id_to_name[track_id] = matched_name
                    
                    if matched_encoding is not None: 
                        tracker_id_to_face_enc[track_id] = matched_encoding
                
                # Penetapan Status
                known_name = tracker_id_to_name.get(track_id)
                current_identity = "VERIFYING..." 

                if known_name:
                    current_identity = known_name # Fix Pegawai
                elif current_age > VERIFICATION_GRACE_PERIOD:
                    current_identity = "PENGUNJUNG"
                
                list_people_on_screen.append({'center': (center_x, center_y), 'identity': current_identity, 'box': box})

                # --- FITUR 1: DETEKSI HP (Peka Overlap > 10%) ---
                if current_identity not in ["PENGUNJUNG", "VERIFYING...", "UNKNOWN"]:
                    is_holding_phone = False
                    for phone_box in list_phones_on_screen:
                        if get_overlap_ratio(phone_box, box) > 0.1:
                            is_holding_phone = True
                            break
                    
                    if is_holding_phone:
                        phone_grace_period[current_identity] = 0 
                        if current_identity not in phone_usage_timers:
                            phone_usage_timers[current_identity] = current_timestamp
                        
                        duration = current_timestamp - phone_usage_timers[current_identity]
                        cv2.putText(frame, f"HP: {int(duration)}s", (x1, y1-30), FONT_STYLE, 0.8, COLOR_RED, 2)
                        
                        if duration > THRESHOLD_PHONE_USAGE_SEC:
                            cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_RED, 4)
                            if current_identity not in phone_violation_reported:
                                queue_log_event("VIOLATION", f"{current_identity} bermain HP")
                                queue_employee_update(current_identity, 0, "Idle (Main HP)")
                                text_to_speech(f"{current_identity}, tolong simpan handphone")
                                phone_violation_reported.add(current_identity)
                    else:
                        if current_identity in phone_usage_timers:
                            grace_counter = phone_grace_period.get(current_identity, 0) + 1
                            phone_grace_period[current_identity] = grace_counter
                            if grace_counter > 30: 
                                del phone_usage_timers[current_identity]
                                phone_grace_period[current_identity] = 0
                                queue_employee_update(current_identity, 0, "Active")
                                if current_identity in phone_violation_reported: 
                                    phone_violation_reported.remove(current_identity)

                # --- FITUR 2: VISITOR COUNTING ---
                if current_identity == "PENGUNJUNG":
                    if (DOOR_LINE_X_POSITION - DOOR_LINE_TOLERANCE < center_x < DOOR_LINE_X_POSITION + DOOR_LINE_TOLERANCE):
                        if track_id not in unique_visitor_ids:
                            curr_enc = tracker_id_to_face_enc.get(track_id)
                            is_returning_visitor = False
                            if curr_enc is not None and len(visitor_face_memory) > 0:
                                matches = face_recognition.compare_faces(visitor_face_memory, curr_enc, tolerance=FACE_REC_TOLERANCE)
                                if True in matches: is_returning_visitor = True
                            unique_visitor_ids.add(track_id)
                            if is_returning_visitor: text_to_speech("Selamat datang kembali")
                            else:
                                visitor_count_total += 1
                                if curr_enc is not None: visitor_face_memory.append(curr_enc)
                                queue_log_event("VISITOR", f"Pelanggan Baru (ID: {track_id})")
                                text_to_speech("Ada pelanggan baru")
                
                box_color = COLOR_GREEN
                if current_identity == "VERIFYING...": box_color = COLOR_YELLOW
                elif current_identity == "PENGUNJUNG": box_color = COLOR_ORANGE
                cv2.putText(frame, current_identity, (x1, y1 - 10), FONT_STYLE, 0.5, box_color, 2)
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

        # 3. Proses Kopi
        for box, cls_id, track_id in zip(boxes, class_ids, tracking_ids):
            if cls_id == CLASS_ID_CUP:
                x1, y1, x2, y2 = box
                cx, cy = int((x1+x2)/2), int((y1+y2)/2)
                is_in_zone = (ZONE_COFFEE_MAKER[0] < cx < ZONE_COFFEE_MAKER[2]) and (ZONE_COFFEE_MAKER[1] < cy < ZONE_COFFEE_MAKER[3])
                
                if track_id not in cup_entry_timestamps:
                    restored = False
                    valid_buffer = [c for c in lost_cups_buffer if current_timestamp - c['lost_time'] < 20.0]
                    lost_cups_buffer = valid_buffer 
                    for i, lost_cup in enumerate(lost_cups_buffer):
                        dist = math.hypot(cx - lost_cup['x'], cy - lost_cup['y'])
                        if dist < 100: 
                            cup_entry_timestamps[track_id] = lost_cup['entry_time']
                            if lost_cup['maker']: cup_maker_assignment[track_id] = lost_cup['maker']
                            del lost_cups_buffer[i]
                            restored = True
                            break
                    if not restored: cup_entry_timestamps[track_id] = current_timestamp

                active_cup_track_ids.add(track_id)
                cup_last_seen_frame[track_id] = frame_counter
                cup_last_coordinates[track_id] = (cx, cy)
                was_in_zone = cup_in_zone_status.get(track_id, False)

                if is_in_zone:
                    nearby_person = get_closest_person((cx, cy), list_people_on_screen)
                    if nearby_person and nearby_person not in ["PENGUNJUNG", "VERIFYING..."]:
                        cup_maker_assignment[track_id] = nearby_person
                        cv2.putText(frame, f"Maker: {nearby_person}", (x1, y2+15), FONT_STYLE, 0.4, COLOR_YELLOW, 1)
                    elapsed_time = int(current_timestamp - cup_entry_timestamps[track_id])
                    color_timer = COLOR_GREEN if elapsed_time > THRESHOLD_COFFEE_BREW_SEC else (200,200,200)
                    cv2.putText(frame, f"{elapsed_time}s", (x1, y1-10), FONT_STYLE, 0.6, color_timer, 2)

                elif not is_in_zone and was_in_zone:
                    maker = cup_maker_assignment.get(track_id)
                    entry_time = cup_entry_timestamps.get(track_id, current_timestamp)
                    duration_work = current_timestamp - entry_time
                    if maker and duration_work > THRESHOLD_COFFEE_BREW_SEC:
                        last_reward_time = cup_cooldown_timers.get(track_id, 0)
                        if current_timestamp - last_reward_time > COOLDOWN_BETWEEN_CUPS_SEC:
                            if maker in employee_daily_score: employee_daily_score[maker] += 1 
                            cup_cooldown_timers[track_id] = current_timestamp
                            queue_employee_update(maker, 1, "Active")
                            queue_log_event("PRODUCTION", f"{maker} selesai kopi")
                            text_to_speech(f"Poin untuk {maker}")
                cup_in_zone_status[track_id] = is_in_zone
                cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_YELLOW, 2)

    # Cleanup Kopi
    for tid in list(cup_in_zone_status.keys()):
        if tid not in active_cup_track_ids and cup_in_zone_status[tid]:
            if frame_counter - cup_last_seen_frame.get(tid, 0) > 10: 
                entry_time = cup_entry_timestamps.get(tid, current_timestamp)
                duration_work = current_timestamp - entry_time
                maker_name = cup_maker_assignment.get(tid)
                last_paid = cup_cooldown_timers.get(tid, 0)
                is_valid = False
                if maker_name and (current_timestamp - last_paid > COOLDOWN_BETWEEN_CUPS_SEC) and (duration_work > THRESHOLD_COFFEE_BREW_SEC):
                    if maker_name in employee_daily_score: employee_daily_score[maker_name] += 1
                    cup_cooldown_timers[tid] = current_timestamp
                    queue_employee_update(maker_name, 1, "Active")
                    queue_log_event("PRODUCTION", f"Kopi diantar {maker_name}")
                    text_to_speech(f"Kopi selesai, poin {maker_name}")
                    is_valid = True
                if not is_valid and duration_work < THRESHOLD_COFFEE_BREW_SEC:
                    last_pos = cup_last_coordinates.get(tid)
                    if last_pos:
                        lost_cups_buffer.append({'x': last_pos[0], 'y': last_pos[1], 'entry_time': entry_time, 'lost_time': current_timestamp, 'maker': maker_name})
                cup_entry_timestamps.pop(tid, None)
                cup_in_zone_status[tid] = False
                if tid in cup_maker_assignment: del cup_maker_assignment[tid]
                if tid in cup_last_coordinates: del cup_last_coordinates[tid]

    if current_timestamp - last_stats_upload_time > INTERVAL_UPLOAD_STATS_SEC:
        queue_visitor_stats(visitor_count_total, len(list_people_on_screen))
        last_stats_upload_time = current_timestamp

    # Overlay
    ui_overlay = frame.copy()
    cv2.rectangle(ui_overlay, (0, 0), (280, 250), (0, 0, 0), -1) 
    cv2.addWeighted(ui_overlay, 0.6, frame, 0.4, 0, frame)
    cv2.putText(frame, f"Visitor: {visitor_count_total}", (10, 30), FONT_STYLE, 0.6, COLOR_GREEN, 2)
    y_position = 60
    for name, score in employee_daily_score.items():
        score_color = COLOR_YELLOW
        if name in phone_usage_timers and (current_timestamp - phone_usage_timers[name] > THRESHOLD_PHONE_USAGE_SEC): score_color = COLOR_RED
        cv2.putText(frame, f"{name}: {score}", (10, y_position), FONT_STYLE, 0.6, score_color, 2)
        y_position += 25

    cv2.imshow("CCTV Smart Monitor (EMPLOYEE MODE)", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

db_task_queue.put(None)
video_capture.release()
cv2.destroyAllWindows()