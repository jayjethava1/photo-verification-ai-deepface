from fastapi import FastAPI
from pydantic import BaseModel
from deepface import DeepFace
import requests
import numpy as np
import cv2
from fastapi import FastAPI, Header, HTTPException
import os

app = FastAPI()

AI_API_KEY = os.getenv("AI_API_KEY")


app = FastAPI()

class VerifyRequest(BaseModel):
    profile_url: str
    selfie_urls: list[str]  # 2–3 selfies

def load_image(url):
    r = requests.get(url, timeout=10)
    img = np.asarray(bytearray(r.content), dtype=np.uint8)
    return cv2.imdecode(img, cv2.IMREAD_COLOR)

def face_distance(img1, img2):
    result = DeepFace.verify(
        img1_path=img1,
        img2_path=img2,
        enforce_detection=True,
        detector_backend="retinaface",
        model_name="ArcFace"
    )
    return result["distance"], result["verified"]
    
@app.post("/verify")
def verify(req: VerifyRequest,    x_api_key: str = Header(None)):

    if not AI_API_KEY or x_api_key != AI_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

    profile = load_image(req.profile_url)

    distances = []
    verified_count = 0

    selfies = [load_image(url) for url in req.selfie_urls]

    # Profile ↔ Selfie checks
    for selfie in selfies:
        dist, ok = face_distance(profile, selfie)
        distances.append(dist)
        if ok:
            verified_count += 1

    avg_profile_distance = sum(distances) / len(distances)

    # Selfie ↔ Selfie uniqueness (only if 2+ selfies)
    inter_distances = []
    if len(selfies) >= 2:
        for i in range(len(selfies)):
            for j in range(i + 1, len(selfies)):
                d, _ = face_distance(selfies[i], selfies[j])
                inter_distances.append(d)

    avg_inter_distance = (
        sum(inter_distances) / len(inter_distances)
        if inter_distances else None
    )

    # Decision logic
    if avg_profile_distance <= 0.35 and (
        avg_inter_distance is None or avg_inter_distance > 0.15
    ):
        decision = "APPROVED"
    elif avg_profile_distance <= 0.45:
        decision = "MANUAL_REVIEW"
    else:
        decision = "REJECTED"

    return {
        "avg_profile_distance": round(avg_profile_distance, 3),
        "avg_inter_distance": (
            round(avg_inter_distance, 3) if avg_inter_distance is not None else None
        ),
        "verified_faces": verified_count,
        "decision": decision
    }

