import hashlib

def generate_door_code(room_number, hostify_id):
    raw = f"{hostify_id}:{room_number}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    num = int(digest, 16) % 10000
    return f"{num:04d}"