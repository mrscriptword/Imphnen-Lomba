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
import certifi
import queue 

# ==========================================
# 0. SETUP DATABASE (WORKER THREAD)
# ==========================================
print("⏳ Menghubungkan ke Database Cloud...")
load_dotenv() 

db_queue = queue.Queue()

def db_worker():
    """Thread khusus upload data agar video tidak lag"""
    try:
        mongo_uri = os.getenv("MONGO_URI")
        # SSL Bypass untuk Windows/Jaringan Kantor
        client = MongoClient(mongo_uri, 
                             tls=True, 
                             tlsAllowInvalidCertificates=True,
                             serverSelectionTimeoutMS=5000)
        
        db = client["I_MBG"]
        col_employees = db["employee_performance"]
        col_logs = db["system_logs"]
        col_visitors = db["visitor_logs"]
        
        client.admin.command('ping')
        print("✅ Database Worker Connected (Background)")
        
    except Exception as e:
        print(f"❌ Database Error: {e}")
        return

    while True:
        try:
            task = db_queue.get()
            if task is None: break 
            
            action, data = task
            if action == "log":
                col_logs.insert_one(data)
                print(f"☁️ Upload Log: {data['event']}")
            elif action == "update_emp":
                col_employees.update_one(
                    {"name": data['name']},
                    {"$inc": {"cups": data['cups_added']}, "$set": {"last_seen": data['ts'], "status": data['status']}},
                    upsert=True
                )
            elif action == "visitor_stats":
                col_visitors.insert_one(data)
            
            db_queue.task_done()
        except Exception as e:
            print(f"⚠️ Gagal Upload: {e}")

threading.Thread(target=db_worker, daemon=True).start()

# Helper Functions
def log_event(event, detail):
    db_queue.put(("log", {"timestamp": datetime.now(), "event": event, "detail": detail}))

def update_employee_db(name, cups_added=0, status="Active"):
    db_queue.put(("update_emp", {"name": name, "cups_added": cups_added, "ts": datetime.now(), "status": status}))

def send_visitor_stats(total_in, current_occupancy):
    db_queue.put(("visitor_stats", {
        "timestamp": datetime.now(), "camera_id": "CAM_MAIN",
        "total_in": total_in, "total_out": 0, "current_occupancy": current_occupancy
    }))

# ==========================================
# 1. SETUP LAINNYA
# ==========================================
def speak(text):
    def run():
        try:
            eng = pyttsx3.init()
            eng.setProperty('rate', 150)
            eng.say(text)
            eng.runAndWait()
        except: pass
    threading.Thread(target=run).start()

print("⏳ Mempelajari wajah pegawai...")
path_folder_wajah = "data_wajah"
known_face_encodings = []
known_face_names = []
employee_stats = {} 

if not os.path.exists(path_folder_wajah): os.makedirs(path_folder_wajah)

for filename in os.listdir(path_folder_wajah):
    if filename.endswith(('.jpg', '.png', '.jpeg')):
        try:
            image_path = os.path.join(path_folder_wajah, filename)
            person_image = face_recognition.load_image_file(image_path)
            encoding = face_recognition.face_encodings(person_image)[0]
            known_face_encodings.append(encoding)
            name = os.path.splitext(filename)[0].upper()
            known_face_names.append(name)
            employee_stats[name] = 0
            print(f"👤 Pegawai Loaded: {name}")
        except: pass

print("⏳ Loading YOLOv8...")
model = YOLO('yolov8n.pt') 
TARGET_CLASSES = [0, 41, 67] 

# ZONA & VISUAL
COFFEE_ZONE = [100, 100, 400, 400] 
FONT = cv2.FONT_HERSHEY_SIMPLEX

# VARIABEL LOGIKA
customer_in_count = 0 
counted_customer_ids = set()
visitor_encodings = [] 
track_id_identity = {} 
track_id_face_enc = {} 

# --- KONFIGURASI TIMER (MODE TESTING) ---
phone_timers = {}        
phone_grace_counter = {} 
violation_reported = set() 
HP_LIMIT_SECONDS = 5     

cup_cooldowns = {} 
COOLDOWN_TIME = 10 
MIN_PRODUCTION_TIME = 5  # 5 Detik untuk test kopi
cup_zone_state = {}
cup_entry_times = {}
cup_last_seen = {}
cup_maker_memory = {} 
GRACE_FRAMES = 15 
lost_cups_buffer = []       
cup_last_coords = {}        
FLICKER_TOLERANCE_SEC = 20.0
FLICKER_DIST_LIMIT = 70     

# Frame Config
frame_idx = 0
FACE_REC_INTERVAL = 5 
last_visitor_sent_time = time.time()
VISITOR_SEND_INTERVAL = 5 

# Geometric Helpers
def is_box_inside(inner_box, outer_box):
    ix1, iy1, ix2, iy2 = inner_box
    ox1, oy1, ox2, oy2 = outer_box
    icx, icy = (ix1+ix2)/2, (iy1+iy2)/2
    return ox1 < icx < ox2 and oy1 < icy < oy2

def get_closest_person_identity(cup_center, people_list, max_dist=400):
    if not people_list: return None
    closest_identity = None
    min_dist = float('inf')
    cx_cup, cy_cup = cup_center
    for person in people_list:
        cx_person, cy_person = person['center']
        dist = math.hypot(cx_cup - cx_person, cy_cup - cy_person)
        if dist < min_dist:
            min_dist = dist
            closest_identity = person['identity']
    if min_dist < max_dist: return closest_identity
    return None

# ==========================================
# MAIN LOOP
# ==========================================
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print("🚀 Sistem Berjalan... (Tekan 'q' untuk stop)")
log_event("SYSTEM", "Sistem Online - Mode Produksi Fix")

while True:
    ret, frame = cap.read()
    if not ret: break
    frame_idx += 1
    current_time = time.time()
    h, w, _ = frame.shape

    # --- A. FACE RECOGNITION ---
    current_faces = [] 
    if frame_idx % FACE_REC_INTERVAL == 0:
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = np.ascontiguousarray(small_frame[:, :, ::-1])
        face_locs = face_recognition.face_locations(rgb_small_frame)
        if len(face_locs) > 0:
            face_encs = face_recognition.face_encodings(rgb_small_frame, face_locs)
            for loc, enc in zip(face_locs, face_encs):
                name = "PENGUNJUNG"
                if len(known_face_encodings) > 0:
                    matches = face_recognition.compare_faces(known_face_encodings, enc, tolerance=0.55)
                    dists = face_recognition.face_distance(known_face_encodings, enc)
                    if len(dists) > 0:
                        best_idx = np.argmin(dists)
                        if matches[best_idx]: name = known_face_names[best_idx]
                top, right, bottom, left = loc
                current_faces.append(((top*4, right*4, bottom*4, left*4), name, enc))

    # --- B. YOLO TRACKING ---
    results = model.track(frame, classes=TARGET_CLASSES, persist=True, verbose=False, conf=0.5, tracker="bytetrack.yaml")
    
    # Area Kopi
    cv2.rectangle(frame, (COFFEE_ZONE[0], COFFEE_ZONE[1]), (COFFEE_ZONE[2], COFFEE_ZONE[3]), (255, 0, 0), 2)

    current_cup_ids = set()
    current_people_detected = [] 
    detected_phones = []

    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
        cls_ids = results[0].boxes.cls.cpu().numpy().astype(int)
        track_ids = results[0].boxes.id.cpu().numpy().astype(int)

        # PASS 1: HP
        for box, cls_id in zip(boxes, cls_ids):
            if cls_id == 67: 
                detected_phones.append(box)
                x1, y1, x2, y2 = box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, "HP", (x1, y1-5), FONT, 0.5, (0,0,255), 1)

        # PASS 2: ORANG & VIOLATION (STICKY TIMER)
        for box, cls_id, track_id in zip(boxes, cls_ids, track_ids):
            if cls_id == 0:
                x1, y1, x2, y2 = box
                cx, cy = int((x1+x2)/2), int((y1+y2)/2)
                
                # Logic Mapping Wajah
                if frame_idx % FACE_REC_INTERVAL == 0:
                    detected_name = None
                    detected_enc = None
                    for face_loc, name, enc in current_faces:
                        if is_box_inside(face_loc, box):
                            detected_name = name
                            detected_enc = enc
                            break
                    if detected_name: track_id_identity[track_id] = detected_name
                    if detected_enc is not None: track_id_face_enc[track_id] = detected_enc
                
                identity = track_id_identity.get(track_id, "PENGUNJUNG")
                current_people_detected.append({'center': (cx, cy), 'identity': identity})

                # --- LOGIKA HP ROBUST ---
                if identity != "PENGUNJUNG":
                    is_holding_phone = False
                    for phone_box in detected_phones:
                        if is_box_inside(phone_box, box):
                            is_holding_phone = True
                            break
                    
                    if is_holding_phone:
                        phone_grace_counter[identity] = 0 
                        if identity not in phone_timers: 
                            phone_timers[identity] = current_time
                            print(f"📱 {identity} mulai pegang HP...")
                        
                        duration = current_time - phone_timers[identity]
                        
                        print(f"⚠️ {identity} HP: {int(duration)}s / {HP_LIMIT_SECONDS}s", end='\r')
                        cv2.putText(frame, f"HP: {int(duration)}s", (x1, y1-30), FONT, 0.8, (0,0,255), 2)
                        
                        if duration > HP_LIMIT_SECONDS:
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 4)
                            if identity not in violation_reported:
                                log_event("VIOLATION", f"{identity} main HP > {HP_LIMIT_SECONDS}s")
                                update_employee_db(identity, 0, "Idle (Main HP)")
                                speak(f"{identity}, tolong simpan handphone")
                                print(f"\n🚨 [SENT] PELANGGARAN: {identity} KE DB!")
                                violation_reported.add(identity)
                    else:
                        if identity in phone_timers:
                            current_grace = phone_grace_counter.get(identity, 0) + 1
                            phone_grace_counter[identity] = current_grace
                            if current_grace < 20: 
                                cv2.putText(frame, "HP LOST?", (x1, y1-30), FONT, 0.6, (0,255,255), 2)
                            else:
                                del phone_timers[identity]
                                phone_grace_counter[identity] = 0
                                update_employee_db(identity, 0, "Active")
                                if identity in violation_reported: violation_reported.remove(identity)
                                print(f"\n✅ {identity} benar-benar menyimpan HP.")
                
                color_name = (0, 255, 0)
                if identity in phone_timers and (current_time - phone_timers[identity] > HP_LIMIT_SECONDS):
                    color_name = (0, 0, 255) 
                cv2.putText(frame, identity, (x1, y1 - 10), FONT, 0.5, color_name, 2)

                # Visitor Logic
                if identity == "PENGUNJUNG":
                    if track_id not in counted_customer_ids:
                        customer_in_count += 1
                        counted_customer_ids.add(track_id)
                        log_event("VISITOR", f"Pelanggan Baru (ID: {track_id})")

        # PASS 3: KOPI (FIX FORMAT STRING UNTUK BACKEND)
        for box, cls_id, track_id in zip(boxes, cls_ids, track_ids):
            if cls_id == 41:
                x1, y1, x2, y2 = box
                cx, cy = int((x1+x2)/2), int((y1+y2)/2)
                in_zone = (COFFEE_ZONE[0] < cx < COFFEE_ZONE[2]) and (COFFEE_ZONE[1] < cy < COFFEE_ZONE[3])
                
                if track_id not in cup_entry_times:
                    restored = False
                    valid_buffer = [c for c in lost_cups_buffer if current_time - c['lost_time'] < FLICKER_TOLERANCE_SEC]
                    lost_cups_buffer = valid_buffer 
                    for i, lost_cup in enumerate(lost_cups_buffer):
                        dist = math.hypot(cx - lost_cup['x'], cy - lost_cup['y'])
                        if dist < FLICKER_DIST_LIMIT:
                            cup_entry_times[track_id] = lost_cup['entry_time']
                            if lost_cup['maker']: cup_maker_memory[track_id] = lost_cup['maker']
                            del lost_cups_buffer[i]
                            restored = True
                            cv2.putText(frame, "RESTORED", (x1, y1-25), FONT, 0.5, (0, 255, 255), 2)
                            break
                    if not restored: cup_entry_times[track_id] = time.time()
                
                current_cup_ids.add(track_id)
                cup_last_seen[track_id] = frame_idx
                cup_last_coords[track_id] = (cx, cy)
                was_in_zone = cup_zone_state.get(track_id, False)

                if in_zone:
                    nearby = get_closest_person_identity((cx, cy), current_people_detected)
                    if nearby and nearby != "PENGUNJUNG":
                        cup_maker_memory[track_id] = nearby
                        cv2.putText(frame, f"Maker: {nearby}", (x1, y2+15), FONT, 0.4, (0,255,255), 1)
                    elapsed = int(current_time - cup_entry_times[track_id])
                    cv2.putText(frame, f"{elapsed}s", (x1, y1-10), FONT, 0.6, (0,255,0), 2)

                elif not in_zone and was_in_zone:
                    maker = cup_maker_memory.get(track_id)
                    entry_time = cup_entry_times.get(track_id, current_time)
                    duration_in_zone = current_time - entry_time
                    if maker and duration_in_zone > MIN_PRODUCTION_TIME:
                        last_paid = cup_cooldowns.get(track_id, 0)
                        if current_time - last_paid > COOLDOWN_TIME:
                            if maker in employee_stats: employee_stats[maker] += 1 
                            cup_cooldowns[track_id] = current_time
                            update_employee_db(maker, 1, "Active")
                            
                            # [PERBAIKAN UTAMA DISINI] Tambahkan kata 'Durasi: '
                            log_event("PRODUCTION", f"{maker} selesai kopi (Durasi: {int(duration_in_zone)}s)")
                            
                            speak(f"Poin untuk {maker}")
                
                cup_zone_state[track_id] = in_zone
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)

    # Cleanup Buffer (Juga diperbaiki)
    for tid in list(cup_zone_state.keys()):
        if tid not in current_cup_ids and cup_zone_state[tid]:
            if frame_idx - cup_last_seen.get(tid, 0) > GRACE_FRAMES:
                entry_time = cup_entry_times.get(tid, current_time)
                duration_in_zone = current_time - entry_time
                maker_name = cup_maker_memory.get(tid)
                last_paid = cup_cooldowns.get(tid, 0)
                is_valid = False
                if maker_name and (current_time - last_paid > COOLDOWN_TIME) and (duration_in_zone > MIN_PRODUCTION_TIME):
                    if maker_name in employee_stats: employee_stats[maker_name] += 1
                    cup_cooldowns[tid] = current_time
                    update_employee_db(maker_name, 1, "Active")
                    
                    # [PERBAIKAN UTAMA DISINI JUGA]
                    log_event("PRODUCTION", f"Kopi diantar {maker_name} (Durasi: {int(duration_in_zone)}s)") 
                    
                    speak(f"Kopi selesai, poin {maker_name}")
                    is_valid = True
                
                if not is_valid and duration_in_zone < MIN_PRODUCTION_TIME:
                    last_pos = cup_last_coords.get(tid)
                    if last_pos:
                        lost_cups_buffer.append({'x': last_pos[0], 'y': last_pos[1], 'entry_time': entry_time, 'lost_time': current_time, 'maker': maker_name})
                cup_entry_times.pop(tid, None)
                cup_zone_state[tid] = False
                if tid in cup_maker_memory: del cup_maker_memory[tid]
                if tid in cup_last_coords: del cup_last_coords[tid]

    if current_time - last_visitor_sent_time > VISITOR_SEND_INTERVAL:
        send_visitor_stats(customer_in_count, len(current_people_detected))
        last_visitor_sent_time = current_time

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (280, 250), (0, 0, 0), -1) 
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    
    cv2.putText(frame, f"Visitor: {customer_in_count}", (10, 30), FONT, 0.6, (0, 255, 0), 2)
    y_pos = 60
    for name, score in employee_stats.items():
        color = (0, 255, 255)
        if name in phone_timers and (current_time - phone_timers[name] > HP_LIMIT_SECONDS): color = (0, 0, 255)
        cv2.putText(frame, f"{name}: {score}", (10, y_pos), FONT, 0.6, color, 2)
        y_pos += 25

    cv2.imshow("Smart Cafe Optimized", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

db_queue.put(None)
cap.release()
cv2.destroyAllWindows()