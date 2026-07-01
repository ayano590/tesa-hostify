hostify_webhook_response = {
    "data": {
        "reservation": {
            "status": "accepted",  # use for status
            "checkIn": "2026-07-03",  # check time format, add exact time, refactor arrival
            "checkOut": "2026-07-06",  # check time format, add exact time, refactor departure
            "custom_fields": [{  # send door_code later to Hostify
                "id": "123456",
                "name": "door_code",
                "value": "None"
            }]
        },
        "listing": {
            "nickname": "4"  # use for room_number
        },
        "guest": {
            "name": "John Doe"  # use for guest_name
        },
        "transactions": []
    },
    "reservation_id": 1234567890,
    "auth": ["secret_key"],
    "action": "new_reservation"
}