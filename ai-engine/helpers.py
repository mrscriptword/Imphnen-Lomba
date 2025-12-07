import os
import cv2
import math
import time
import queue
import threading
import pyttsx3
import face_recognition
import numpy as np
from datetime import datetime
from pymongo import MongoClient

# ==========================================
# 1. DATABASE HANDLER
# ==========================================
class DatabaseHandler:
    def __init__(self, mongo_uri, db_name="I_MBG"):
        self.queue = queue.Queue()
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        # Jalankan worker di background
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            client = MongoClient(self.mongo_uri, tls=True, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)
            db = client[self.db_name]
            self.col_employees = db["employee_performance"]
            self.col_logs = db["system_logs"]
            self.col_visitors = db["visitor_logs"]
            print("✅ [DB] Database Connected Successfully")
        except Exception as e:
            print(f"❌ [DB] Connection Error: {e}")
            return

        while True:
            task = self.queue.get()
            if task is None: break
            action, payload = task
            try:
                if action == "log":
                    self.col_logs.insert_one(payload)
                    print(f"☁️ [LOG] {payload['event']}")
                elif action == "update_emp":
                    self.col_employees.update_one(
                        {"name": payload['name']},
                        {"$inc": {"cups": payload['cups']}, "$set": {"last_seen": payload['ts'], "status": payload['status']}},
                        upsert=True
                    )
                elif action == "visitor":
                    self.col_visitors.insert_one(payload)
            except Exception as e:
                print(f"⚠️ [DB] Error: {e}")
            self.queue.task_done()

    def log_event(self, event, detail):
        self.queue.put(("log", {"timestamp": datetime.now(), "event": event, "detail": detail}))

    def update_employee(self, name, cups=0, status="Active"):
        self.queue.put(("update_emp", {"name": name, "cups": cups, "ts": datetime.now(), "status": status}))

    def log_visitor(self, total_in, occupancy):
        self.queue.put(("visitor", {"timestamp": datetime.now(), "camera_id": "CAM_MAIN", "total_in": total_in, "current_occupancy": occupancy}))

# ==========================================
# 2. FACE MONITOR (HOT RELOAD)
# ==========================================
class FaceMonitor:
    def __init__(self, folder_path="data_wajah"):
        self.path = folder_path
        self.encodings = []
        self.names = []
        self.new_faces_detected = [] # Untuk notifikasi ke main loop
        
        if not os.path.exists(self.path): os.makedirs(self.path)
        
        # Load awal
        self.load_faces()
        # Jalan monitoring
        threading.Thread(target=self._monitor, daemon=True).start()

    def load_faces(self):
        print("🔄 [SYSTEM] Reloading Face Database...")
        temp_enc = []
        temp_names = []
        
        if not os.path.exists(self.path): return

        for filename in os.listdir(self.path):
            if filename.endswith(('.jpg', '.png', '.jpeg')):
                try:
                    name = os.path.splitext(filename)[0].upper()
                    # Optimasi: Skip jika sudah ada di memori (logic sederhana)
                    # Tapi untuk keamanan reload total, kita baca ulang atau bisa diimprove cachingnya
                    img_path = os.path.join(self.path, filename)
                    img = face_recognition.load_image_file(img_path)
                    encs = face_recognition.face_encodings(img)
                    
                    if encs:
                        temp_enc.append(encs[0])
                        temp_names.append(name)
                        if name not in self.names:
                            self.new_faces_detected.append(name)
                except: pass
        
        self.encodings = temp_enc
        self.names = temp_names
        print(f"✅ [SYSTEM] Total Wajah: {len(self.names)}")

    def _monitor(self):
        last_count = len(os.listdir(self.path))
        while True:
            time.sleep(5)
            try:
                curr_count = len(os.listdir(self.path))
                if curr_count != last_count:
                    print("📂 [DETECT] Perubahan data wajah! Reloading...")
                    time.sleep(1)
                    self.load_faces()
                    last_count = curr_count
            except: pass

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def text_to_speech(text):
    def run():
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.say(text)
            engine.runAndWait()
        except: pass
    threading.Thread(target=run).start()

def get_overlap_ratio(box_small, box_large):
    xA = max(box_small[0], box_large[0])
    yA = max(box_small[1], box_large[1])
    xB = min(box_small[2], box_large[2])
    yB = min(box_small[3], box_large[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxSmallArea = (box_small[2] - box_small[0]) * (box_small[3] - box_small[1])
    return interArea / float(boxSmallArea) if boxSmallArea > 0 else 0

def is_face_aligned_with_body(face_box, body_box):
    fx1, fy1, fx2, fy2 = face_box
    bx1, by1, bx2, by2 = body_box
    face_cx = (fx1 + fx2) / 2
    face_cy = (fy1 + fy2) / 2
    body_cx = (bx1 + bx2) / 2
    
    x_aligned = abs(face_cx - body_cx) < (bx2 - bx1) * 0.8 
    body_upper = by1 - (by2 - by1) * 0.3 
    body_chest = by1 + (by2 - by1) * 0.5
    return x_aligned and (body_upper < face_cy < body_chest)

def get_closest_person(target_center, people_list, max_distance=600):
    if not people_list: return None
    closest, min_dist = None, float('inf')
    tx, ty = target_center
    for p in people_list:
        px, py = p['center']
        dist = math.hypot(tx - px, ty - py)
        if dist < min_dist:
            min_dist, closest = dist, p['identity']
    return closest if min_dist < max_distance else None