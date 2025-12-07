import cv2
import time
import os
import math
import numpy as np
import face_recognition
from ultralytics import YOLO
from dotenv import load_dotenv
# IMPORT DARI FILE HELPERS
from helpers import DatabaseHandler, FaceMonitor, text_to_speech, get_overlap_ratio, is_face_aligned_with_body, get_closest_person

# 1. SETUP & CONFIG
load_dotenv()
cam_idx = int(os.getenv('CAMERA_INDEX', 0))
db = DatabaseHandler(os.getenv("MONGO_URI"))
face_engine = FaceMonitor("data_wajah") # Auto Hot Reload aktif
model = YOLO('yolov8n.pt')

# Konstanta
CLASSES = [0, 41, 67] # Person, Cup, Phone
ZONE_COFFEE = [100, 100, 400, 400]
DOOR_X = 300
CONFIDENCE = 0.35
FONT = cv2.FONT_HERSHEY_SIMPLEX
COLORS = {'RED': (0,0,255), 'GREEN': (0,255,0), 'YELLOW': (0,255,255), 'ORANGE': (0,165,255)}

# State Variables
employee_scores = {}
visitor_total = 0
unique_visitors = set()
visitor_face_mem = []
track_map = {'name': {}, 'enc': {}, 'age': {}}
timers = {'phone': {}, 'phone_grace': {}, 'cup_cool': {}, 'cup_entry': {}, 'cup_last': {}}
cup_states = {'in_zone': {}, 'maker': {}, 'coords': {}, 'buffer': []}
reported_violations = set()

cap = cv2.VideoCapture(cam_idx)
cap.set(3, 640); cap.set(4, 480)
db.log_event("SYSTEM", "AI Engine Started (Modular Version)")
frame_count = 0
last_upload = time.time()

print("🚀 Smart Cafe AI Started...")

while True:
    ret, frame = cap.read()
    if not ret: break
    frame_count += 1
    now = time.time()
    H, W, _ = frame.shape

    # --- SYNCHRONIZE SCORES (Jika ada wajah baru dari Hot Reload) ---
    for new_name in face_engine.new_faces_detected:
        if new_name not in employee_scores: employee_scores[new_name] = 0
    face_engine.new_faces_detected.clear() # Reset flag

    # --- A. FACE RECOGNITION ---
    faces_in_frame = []
    if frame_count % 3 == 0:
        small = cv2.resize(frame, (0,0), fx=0.25, fy=0.25)
        rgb = np.ascontiguousarray(small[:,:,::-1])
        locs = face_recognition.face_locations(rgb)
        if locs:
            encs = face_recognition.face_encodings(rgb, locs)
            for loc, enc in zip(locs, encs):
                top, right, bottom, left = loc
                scaled = (top*4, right*4, bottom*4, left*4)
                name = "UNKNOWN"
                if face_engine.encodings:
                    matches = face_recognition.compare_faces(face_engine.encodings, enc, tolerance=0.6)
                    dists = face_recognition.face_distance(face_engine.encodings, enc)
                    if len(dists) > 0:
                        best = np.argmin(dists)
                        if matches[best]: name = face_engine.names[best]
                faces_in_frame.append((scaled, name, enc))

    # --- B. YOLO TRACKING ---
    res = model.track(frame, classes=CLASSES, persist=True, verbose=False, conf=CONFIDENCE, tracker="bytetrack.yaml")
    
    # Draw Zones
    cv2.rectangle(frame, (ZONE_COFFEE[0], ZONE_COFFEE[1]), (ZONE_COFFEE[2], ZONE_COFFEE[3]), COLORS['RED'], 2)
    cv2.line(frame, (DOOR_X, 0), (DOOR_X, H), COLORS['YELLOW'], 2)

    active_cups = set()
    people_on_scr = []
    phones_on_scr = []

    if res[0].boxes.id is not None:
        boxes = res[0].boxes.xyxy.cpu().numpy().astype(int)
        clss = res[0].boxes.cls.cpu().numpy().astype(int)
        tids = res[0].boxes.id.cpu().numpy().astype(int)

        # 1. Collect Phones
        for box, cls in zip(boxes, clss):
            if cls == 67: 
                phones_on_scr.append(box)
                cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), COLORS['RED'], 2)

        # 2. Process People
        for box, cls, tid in zip(boxes, clss, tids):
            if cls == 0:
                track_map['age'][tid] = track_map['age'].get(tid, 0) + 1
                
                # Match Identity
                if frame_count % 3 == 0:
                    for floc, fname, fenc in faces_in_frame:
                        if is_face_aligned_with_body(floc, box):
                            if fname != "UNKNOWN": track_map['name'][tid] = fname
                            track_map['enc'][tid] = fenc
                            break
                
                identity = track_map['name'].get(tid)
                if not identity:
                    identity = "PENGUNJUNG" if track_map['age'][tid] > 10 else "VERIFYING..."
                
                cx, cy = int((box[0]+box[2])/2), int((box[1]+box[3])/2)
                people_on_scr.append({'center': (cx, cy), 'identity': identity, 'box': box})

                # > LOGIC: PHONE VIOLATION
                if identity not in ["PENGUNJUNG", "VERIFYING..."]:
                    holding = any(get_overlap_ratio(pbox, box) > 0.1 for pbox in phones_on_scr)
                    if holding:
                        timers['phone_grace'][identity] = 0
                        if identity not in timers['phone']: timers['phone'][identity] = now
                        dur = now - timers['phone'][identity]
                        cv2.putText(frame, f"HP: {int(dur)}s", (box[0], box[1]-30), FONT, 0.8, COLORS['RED'], 2)
                        if dur > 3:
                            cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), COLORS['RED'], 4)
                            if identity not in reported_violations:
                                db.log_event("VIOLATION", f"{identity} main HP")
                                db.update_employee(identity, 0, "Idle (HP)")
                                text_to_speech(f"{identity}, simpan HP")
                                reported_violations.add(identity)
                    else:
                        if identity in timers['phone']:
                            timers['phone_grace'][identity] = timers['phone_grace'].get(identity, 0) + 1
                            if timers['phone_grace'][identity] > 30:
                                del timers['phone'][identity]
                                reported_violations.discard(identity)
                                db.update_employee(identity, 0, "Active")

                # > LOGIC: VISITOR
                elif identity == "PENGUNJUNG":
                    if DOOR_X - 30 < cx < DOOR_X + 30:
                        if tid not in unique_visitors:
                            enc = track_map['enc'].get(tid)
                            is_return = False
                            if enc is not None and visitor_face_mem:
                                if True in face_recognition.compare_faces(visitor_face_mem, enc, 0.6): is_return = True
                            
                            unique_visitors.add(tid)
                            msg = "Selamat datang kembali" if is_return else "Pelanggan baru"
                            text_to_speech(msg)
                            if not is_return:
                                visitor_total += 1
                                if enc is not None: visitor_face_mem.append(enc)
                                db.log_event("VISITOR", f"New Visitor ID: {tid}")

                color = COLORS['GREEN'] if identity not in ["PENGUNJUNG", "VERIFYING..."] else COLORS['ORANGE']
                cv2.putText(frame, identity, (box[0], box[1]-10), FONT, 0.5, color, 2)
                cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), color, 2)

        # 3. Process Cups
        for box, cls, tid in zip(boxes, clss, tids):
            if cls == 41:
                cx, cy = int((box[0]+box[2])/2), int((box[1]+box[3])/2)
                in_zone = (ZONE_COFFEE[0] < cx < ZONE_COFFEE[2]) and (ZONE_COFFEE[1] < cy < ZONE_COFFEE[3])
                
                # Buffer Logic (Recover Lost Tracking)
                if tid not in timers['cup_entry']:
                    restored = False
                    cup_states['buffer'] = [c for c in cup_states['buffer'] if now - c['lost'] < 20]
                    for i, lost in enumerate(cup_states['buffer']):
                        if math.hypot(cx - lost['x'], cy - lost['y']) < 100:
                            timers['cup_entry'][tid] = lost['entry']
                            cup_states['maker'][tid] = lost['maker']
                            del cup_states['buffer'][i]; restored = True; break
                    if not restored: timers['cup_entry'][tid] = now

                active_cups.add(tid)
                cup_states['coords'][tid] = (cx, cy)
                cup_states['in_zone'][tid] = in_zone # Fix logic var

                if in_zone:
                    maker = get_closest_person((cx, cy), people_on_scr)
                    if maker and maker not in ["PENGUNJUNG", "VERIFYING..."]:
                        cup_states['maker'][tid] = maker
                        cv2.putText(frame, f"Maker: {maker}", (box[0], box[3]+15), FONT, 0.4, COLORS['YELLOW'], 1)
                    
                    elapsed = int(now - timers['cup_entry'][tid])
                    col_t = COLORS['GREEN'] if elapsed > 4 else (200,200,200)
                    cv2.putText(frame, f"{elapsed}s", (box[0], box[1]-10), FONT, 0.6, col_t, 2)
                
                elif not in_zone and cup_states.get('was_in_zone', {}).get(tid, False):
                    # Logic kopi selesai -> moved to cleanup below usually, but simplified here
                    pass

                cup_states.setdefault('was_in_zone', {})[tid] = in_zone
                cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), COLORS['YELLOW'], 2)

    # Cleanup Cups (Reward Logic)
    for tid in list(cup_states.get('was_in_zone', {}).keys()):
        if tid not in active_cups and cup_states['was_in_zone'][tid]:
            entry = timers['cup_entry'].get(tid, now)
            dur = now - entry
            maker = cup_states['maker'].get(tid)
            last_pay = timers['cup_cool'].get(tid, 0)
            
            if maker and (now - last_pay > 10) and (dur > 4):
                if maker in employee_scores: employee_scores[maker] += 1
                timers['cup_cool'][tid] = now
                db.update_employee(maker, 1, "Active")
                db.log_event("PRODUCTION", f"{maker} selesai kopi ({int(dur)}s)")
                text_to_speech(f"Poin untuk {maker}")
            elif dur < 4:
                # Save to buffer
                lpos = cup_states['coords'].get(tid)
                if lpos: cup_states['buffer'].append({'x': lpos[0], 'y': lpos[1], 'entry': entry, 'lost': now, 'maker': maker})
            
            # Clean dicts
            timers['cup_entry'].pop(tid, None)
            cup_states['was_in_zone'][tid] = False

    # Stats Upload
    if now - last_upload > 5:
        db.log_visitor(visitor_total, len(people_on_scr))
        last_upload = now

    # UI Overlay
    ovl = frame.copy()
    cv2.rectangle(ovl, (0,0), (280, 250), (0,0,0), -1)
    cv2.addWeighted(ovl, 0.6, frame, 0.4, 0, frame)
    cv2.putText(frame, f"Visitor: {visitor_total}", (10, 30), FONT, 0.6, COLORS['GREEN'], 2)
    y_pos = 60
    for nm, sc in employee_scores.items():
        col = COLORS['RED'] if nm in timers['phone'] and (now - timers['phone'][nm] > 3) else COLORS['YELLOW']
        cv2.putText(frame, f"{nm}: {sc}", (10, y_pos), FONT, 0.6, col, 2)
        y_pos += 25

    cv2.imshow("CCTV AI (Modular)", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()