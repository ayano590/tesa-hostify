hw_new_reservation_response = {
    "data": {
        "reservation": {
            "status": "accepted",
            "checkIn": "2026-07-03",
            "checkOut": "2026-07-06",
            "custom_fields": [{
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
        }
    },
    "reservation_id": 1234567890,
    "action": "new_reservation"
}

hw_update_reservation_response = {
    "planned_arrival": "16:00:00",
    "planned_departure": "11:00:00",
    "checkIn": "2026-07-03",
    "checkOut": "2026-07-06",
    "status_code": "8",  # cancelled
    "reservation_id": "1234567890",
    "action": "update_reservation"
}

hw_move_reservation_response = {
    "data": {
        "listing": {
            "nickname": "5"
        }
    },
    "reservation_id": "1234567890",
    "action": "move_reservation"
}

hostify_webhook_event_types = [
    "message_new",
    "move_reservation",
    "new_reservation",
    "update_reservation",
    "create_listing",
    "update_listing",
    "create_update_listing",
    "listing_photo_processed"
]

hostify_update_reservation_custom_field = {
    "reservation_id": 1234567890,
    "custom_field_id": 123456,
    "value": "string"
}