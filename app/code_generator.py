import hashlib

def generate_door_code(room_number, reservation_id):
    raw = f"{reservation_id}:{room_number}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    num = int(digest, 16) % 10000
    return f"{num:04d}"