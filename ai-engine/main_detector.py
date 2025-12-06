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

# ==========================================
# 0. SETUP DATABASE (MONGODB CLOUD)
# ==========================================
print("⏳ Menghubungkan ke Database Cloud...")
load_dotenv() # Load password dari file .env

try:
    mongo_uri = os.getenv("MONGO_URI")
    # certifi diperlukan untuk koneksi SSL yang aman
    client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
    db = client["I_MBG"] # Pastikan nama database SAMA dengan di MongoDB Atlas
    
    # Definisi Collection (Tabel)
    col_employees = db["employee_performance"] # Data Pegawai & Kopi
    col_logs = db["system_logs"]               # Log Kejadian
    col_visitors = db["visitor_logs"]          # Data Grafik Pengunjung
    
    print("✅ Berhasil terkoneksi ke MongoDB Atlas!")
except Exception as e:
    print(f"❌ Gagal koneksi Database: {e}")
    exit()

# --- FUNGSI DATABASE HELPER ---
def log_event(event, detail):
    """Mencatat kejadian penting ke MongoDB (Log)"""
    try:
        log_data = {
            "timestamp": datetime.now(),
            "event": event,
            "detail": detail
        }
        col_logs.insert_one(log_data)
        print(f"📝 Log: {event} - {detail}")
    except Exception as e:
        print(f"⚠️ Gagal simpan log: {e}")

def update_employee_db(name, cups_added=0, status="Active"):
    """Update data pegawai (Upsert: Update jika ada, Buat baru jika tidak)"""
    try:
        ts = datetime.now()
        col_employees.update_one(
            {"name": name}, # Filter cari nama
            {
                "$inc": {"cups": cups_added}, # Increment jumlah kopi
                "$set": {
                    "last_seen": ts,
                    "status": status
                }
            },
            upsert=True # Buat data baru jika nama belum ada
        )
    except Exception as e:
        print(f"⚠️ Gagal update pegawai: {e}")

def send_visitor_stats(total_in, current_occupancy):
    """Kirim data statistik pengunjung untuk Grafik Dashboard"""
    try:
        col_visitors.insert_one({
            "timestamp": datetime.now(),
            "camera_id": "CAM_MAIN",
            "total_in": total_in,
            "total_out": 0, # Logic out belum ada, set 0 dulu
            "current_occupancy": current_occupancy
        })
    except Exception as e:
        print(f"⚠️ Gagal kirim statistik visitor: {e}")

# ==========================================
# 1. SETUP SUARA
# ==========================================
def speak(text):
    def run():
        try:
            eng = pyttsx3.init()
            eng.setProperty('rate', 150)
            eng.setProperty('volume', 1.0)
            eng.say(text)
            eng.runAndWait()
        except: pass
    threading.Thread(target=run).start()

# ==========================================
# 2. SETUP WAJAH (FACE RECOGNITION)
# ==========================================
print("⏳ Mempelajari wajah pegawai...")
path_folder_wajah = "data_wajah" # Pastikan folder ini ada dan berisi foto
known_face_encodings = []
known_face_names = []
employee_stats = {} 

if not os.path.exists(path_folder_wajah):
    os.makedirs(path_folder_wajah)

for filename in os.listdir(path_folder_wajah):
    if filename.endswith(('.jpg', '.png', '.jpeg')):
        image_path = os.path.join(path_folder_wajah, filename)
        person_image = face_recognition.load_image_file(image_path)
        try:
            encoding = face_recognition.face_encodings(person_image)[0]
            known_face_encodings.append(encoding)
            
            # Nama file jadi nama pegawai (contoh: "budi.jpg" -> "BUDI")
            name = os.path.splitext(filename)[0].upper()
            known_face_names.append(name)
            
            # Inisialisasi data lokal & database
            employee_stats[name] = 0
            update_employee_db(name, 0, "Ready")
            print(f"👤 Pegawai Loaded: {name}")
        except IndexError:
            print(f"⚠️ Wajah tidak terdeteksi di file: {filename}")
            pass

# ==========================================
# 3. VARIABEL & SETTING DETEKSI
# ==========================================
print("⏳ Loading YOLOv8...")
model = YOLO('yolov8n.pt') 
TARGET_CLASSES = [0, 41, 67] # 0=Person, 41=Cup, 67=Cell Phone

# ZONA DETEKSI (Sesuaikan dengan posisi kamera Anda)
LINE_POSITION = 300 
OFFSET = 30 
COFFEE_ZONE = [100, 100, 400, 400] 
FONT = cv2.FONT_HERSHEY_SIMPLEX

# VARIABEL DATA
customer_in_count = 0 
counted_customer_ids = set()
visitor_encodings = [] 
track_id_identity = {} 
track_id_face_enc = {} 
phone_timers = {}        
HP_LIMIT_SECONDS = 120  

# STATE KOPI & BUFFER (Anti-Flicker Logic)
cup_cooldowns = {} 
COOLDOWN_TIME = 30 
MIN_PRODUCTION_TIME = 120 
cup_zone_state = {}
cup_entry_times = {}
cup_last_seen = {}
cup_maker_memory = {} 
GRACE_FRAMES = 15 

# Buffer Data Hilang
lost_cups_buffer = []       
cup_last_coords = {}        
FLICKER_TOLERANCE_SEC = 20.0
FLICKER_DIST_LIMIT = 70     

frame_idx = 0
process_this_frame = True 
last_visitor_sent_time = time.time()
VISITOR_SEND_INTERVAL = 5 # Kirim data ke web setiap 5 detik

# --- FUNGSI BANTU MATEMATIKA ---
def is_box_inside(inner_box, outer_box):
    ix1, iy1, ix2, iy2 = inner_box
    ox1, oy1, ox2, oy2 = outer_box
    icx, icy = (ix1+ix2)/2, (iy1+iy2)/2
    return ox1 < icx < ox2 and oy1 < icy < oy2

def get_closest_person_identity(cup_center, people_list, max_dist=350):
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
# 4. MAIN LOOP (LOOP UTAMA)
# ==========================================
cap = cv2.VideoCapture(0)
speak("Sistem Deteksi Siap") 
log_event("SYSTEM", "Aplikasi dimulai")

print("🚀 Sistem Berjalan. Tekan 'q' untuk keluar.")

while True:
    ret, frame = cap.read()
    if not ret: break
    frame_idx += 1
    h, w, _ = frame.shape
    current_time = time.time()

    # --- A. FACE RECOGNITION (Setiap frame genap/ganjil biar ringan) ---
    current_faces = [] 
    if process_this_frame:
        # Resize gambar ke 1/4 ukuran biar cepat
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = np.ascontiguousarray(small_frame[:, :, ::-1])
        
        # Deteksi wajah
        face_locs = face_recognition.face_locations(rgb_small_frame)
        face_encs = face_recognition.face_encodings(rgb_small_frame, face_locs)

        for loc, enc in zip(face_locs, face_encs):
            name = "PENGUNJUNG"
            # Bandingkan dengan data pegawai
            matches = face_recognition.compare_faces(known_face_encodings, enc, tolerance=0.55)
            dists = face_recognition.face_distance(known_face_encodings, enc)
            
            if len(dists) > 0:
                best_idx = np.argmin(dists)
                if matches[best_idx]: name = known_face_names[best_idx]
            
            # Kembalikan koordinat ke ukuran asli (dikali 4)
            top, right, bottom, left = loc
            current_faces.append(((top*4, right*4, bottom*4, left*4), name, enc))
    
    process_this_frame = not process_this_frame

    # --- B. YOLO TRACKING ---
    results = model.track(frame, classes=TARGET_CLASSES, persist=True, verbose=False, tracker="bytetrack.yaml")
    
    # Visualisasi Zona
    cv2.line(frame, (LINE_POSITION, 0), (LINE_POSITION, h), (0, 255, 255), 2)
    cv2.rectangle(frame, (COFFEE_ZONE[0], COFFEE_ZONE[1]), (COFFEE_ZONE[2], COFFEE_ZONE[3]), (255, 0, 0), 2)

    current_cup_ids = set()
    current_people_detected = [] # List orang di frame ini
    detected_phones = []

    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
        cls_ids = results[0].boxes.cls.cpu().numpy().astype(int)
        track_ids = results[0].boxes.id.cpu().numpy().astype(int)

        # PASS 1: DETEKSI HP
        for box, cls_id in zip(boxes, cls_ids):
            if cls_id == 67: # Cell Phone
                detected_phones.append(box)
                x1, y1, x2, y2 = box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

        # PASS 2: DETEKSI ORANG & IDENTIFIKASI
        for box, cls_id, track_id in zip(boxes, cls_ids, track_ids):
            if cls_id == 0: # Person
                x1, y1, x2, y2 = box
                cx, cy = int((x1+x2)/2), int((y1+y2)/2)
                
                # Coba cocokkan kotak YOLO dengan kotak Wajah
                detected_name = None
                detected_enc = None
                for face_loc, name, enc in current_faces:
                    if is_box_inside(face_loc, box):
                        detected_name = name
                        detected_enc = enc
                        break
                
                # Simpan identitas ke memori tracking
                if detected_name: track_id_identity[track_id] = detected_name
                if detected_enc is not None: track_id_face_enc[track_id] = detected_enc
                
                # Ambil identitas (default: PENGUNJUNG)
                identity = track_id_identity.get(track_id, "PENGUNJUNG")
                current_people_detected.append({'center': (cx, cy), 'identity': identity})

                # --- LOGIKA MAIN HP ---
                if identity != "PENGUNJUNG":
                    is_holding_phone = False
                    for phone_box in detected_phones:
                        if is_box_inside(phone_box, box):
                            is_holding_phone = True
                            break
                    
                    if is_holding_phone:
                        if identity not in phone_timers: phone_timers[identity] = current_time
                        duration = current_time - phone_timers[identity]
                        
                        # Jika main HP terlalu lama
                        if duration > HP_LIMIT_SECONDS:
                            if int(duration) % 5 == 0:
                                update_employee_db(identity, 0, "Idle (Main HP)")
                                if int(duration) == HP_LIMIT_SECONDS + 1:
                                    log_event("VIOLATION", f"{identity} main HP > {HP_LIMIT_SECONDS}s")
                                    speak(f"{identity}, tolong simpan handphone")
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    else:
                        # Reset timer jika HP disimpan
                        if identity in phone_timers:
                            del phone_timers[identity]
                            update_employee_db(identity, 0, "Active")
                
                cv2.putText(frame, identity, (x1, y1 - 10), FONT, 0.5, (0, 255, 0), 2)

                # --- LOGIKA VISITOR COUNTING ---
                if identity == "PENGUNJUNG":
                    if LINE_POSITION - OFFSET < cx < LINE_POSITION + OFFSET:
                        if track_id not in counted_customer_ids:
                            # Cek Re-identification (Pelanggan lama balik lagi?)
                            current_encoding = track_id_face_enc.get(track_id)
                            is_returning = False
                            if current_encoding is not None and len(visitor_encodings) > 0:
                                matches = face_recognition.compare_faces(visitor_encodings, current_encoding, tolerance=0.50)
                                if True in matches: is_returning = True
                            
                            if is_returning:
                                counted_customer_ids.add(track_id) 
                                speak("Selamat datang kembali") 
                            else:
                                customer_in_count += 1
                                counted_customer_ids.add(track_id)
                                if current_encoding is not None: visitor_encodings.append(current_encoding)
                                log_event("VISITOR", f"Pelanggan Baru (ID: {track_id})")
                                speak("Ada pelanggan baru")

        # PASS 3: LOGIKA PRODUKSI KOPI (DENGAN ANTI-FLICKER BUFFER)
        for box, cls_id, track_id in zip(boxes, cls_ids, track_ids):
            if cls_id == 41: # CUP
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
                            if lost_cup['maker']:
                                cup_maker_memory[track_id] = lost_cup['maker']
                            del lost_cups_buffer[i]
                            restored = True
                            cv2.putText(frame, "RESTORED", (x1, y1-25), FONT, 0.5, (0, 255, 255), 2)
                            break
                    
                    if not restored:
                        cup_entry_times[track_id] = time.time() # Gelas Baru
                
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
                    color_t = (0,255,0) if elapsed > MIN_PRODUCTION_TIME else (200,200,200)
                    cv2.putText(frame, f"{elapsed}s", (x1, y1-10), FONT, 0.6, color_t, 2)

                elif not in_zone and was_in_zone:
                    # Gelas keluar dari zona (Selesai?)
                    maker = cup_maker_memory.get(track_id)
                    entry_time = cup_entry_times.get(track_id, current_time)
                    duration_in_zone = current_time - entry_time
                    
                    if maker:
                        if duration_in_zone > MIN_PRODUCTION_TIME:
                            last_paid = cup_cooldowns.get(track_id, 0)
                            if current_time - last_paid > COOLDOWN_TIME:
                                if maker in employee_stats:
                                    employee_stats[maker] += 1 
                                    cup_cooldowns[track_id] = current_time
                                    
                                    # --- UPDATE DATABASE CLOUD ---
                                    update_employee_db(maker, 1, "Active")
                                    log_event("PRODUCTION", f"{maker} menyelesaikan 1 Kopi ({int(duration_in_zone)}s)")
                                    
                                    speak(f"Poin kopi untuk {maker}")
                        else:
                            cv2.putText(frame, "IGNORED (<2m)", (x1, y1-10), FONT, 0.5, (0,0,255), 2)
                
                cup_zone_state[track_id] = in_zone
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)

    for tid in list(cup_zone_state.keys()):
        if tid not in current_cup_ids and cup_zone_state[tid]:
            if frame_idx - cup_last_seen.get(tid, 0) > GRACE_FRAMES:
                entry_time = cup_entry_times.get(tid, current_time)
                duration_in_zone = current_time - entry_time
                maker_name = cup_maker_memory.get(tid)
                last_paid = cup_cooldowns.get(tid, 0)
                
                is_valid = False
                if maker_name and (current_time - last_paid > COOLDOWN_TIME) and (duration_in_zone > MIN_PRODUCTION_TIME):
                    if maker_name in employee_stats:
                        employee_stats[maker_name] += 1
                        cup_cooldowns[tid] = current_time
                        update_employee_db(maker_name, 1, "Active")
                        log_event("PRODUCTION", f"Kopi diantar oleh {maker_name} (Durasi: {int(duration_in_zone)}s)")
                        
                        speak(f"Kopi selesai, poin untuk {maker_name}")
                        is_valid = True
                if not is_valid and duration_in_zone < MIN_PRODUCTION_TIME:
                    last_pos = cup_last_coords.get(tid)
                    if last_pos:
                        lost_cups_buffer.append({
                            'x': last_pos[0], 'y': last_pos[1],
                            'entry_time': entry_time,
                            'lost_time': current_time,
                            'maker': maker_name
                        })
                cup_entry_times.pop(tid, None)
                cup_zone_state[tid] = False
                if tid in cup_maker_memory: del cup_maker_memory[tid]
                if tid in cup_last_coords: del cup_last_coords[tid]
    if current_time - last_visitor_sent_time > VISITOR_SEND_INTERVAL:
        current_occupancy = len(current_people_detected)
        send_visitor_stats(customer_in_count, current_occupancy)
        print(f"📡 Update Web: Visitor={customer_in_count}, Occupancy={current_occupancy}")
        last_visitor_sent_time = current_time

    # ==========================================
    # 6. VISUALISASI UI
    # ==========================================
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (280, 300), (0, 0, 0), -1) 
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    y_pos = 30
    cv2.putText(frame, f"Total Visitor: {customer_in_count}", (10, y_pos), FONT, 0.6, (0, 255, 0), 2)
    y_pos += 30
    cv2.putText(frame, "--- KINERJA PEGAWAI ---", (10, y_pos), FONT, 0.5, (255, 255, 255), 1)
    
    for name, score in employee_stats.items():
        y_pos += 25
        status_color = (0, 255, 255)
        # Tandai merah jika sedang melanggar aturan HP
        if name in phone_timers and (current_time - phone_timers[name] > HP_LIMIT_SECONDS):
            status_color = (0, 0, 255) 
        cv2.putText(frame, f"{name}: {score} Cups", (10, y_pos), FONT, 0.6, status_color, 2)

    cv2.imshow("Smart Cafe AI System (MongoDB Connected)", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
client.close()
print("Sistem Berhenti.")