hostify_webhook_response = {
    "data": {
        "reservation": {
            "status": "accepted",
            "checkIn": "2026-07-03",
            "checkOut": "2026-07-06",
            "custom_fields": [{  # send door_code later to Hostify
                "id": "123456",
                "name": "door_code",
                "value": "None"
            }]
        },
        "listing": {
            "nickname": "4"
        },
        "guest": {
            "name": "John Doe"
        },
        "transactions": []
    },
    "reservation_id": 1234567890,
    "auth": ["secret_key"],
    "action": "new_reservation"
}