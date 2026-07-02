call init_db() on server PC when going live

Dashboard > Networking > Tunnels > "your tunnel name" > Overview
Computer\HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Cloudflared\ImagePath

curl -X 'GET' 'https://api-rms.hostify.com/webhooks_v2' -H 'accept: */*' -H 'x-api-key: api-key'
curl -X 'POST' 'https://api-rms.hostify.com/webhooks_v2' -H 'accept: */*' -H 'x-api-key: api-key' -H 'Content-Type: application/json' -d '{"url": "https://api.example.com/webhook", "notification_type": "message_new", "auth": "string"}'
curl -X 'DELETE' 'https://api-rms.hostify.com/webhooks_v2/{id}' -H 'accept: */*' -H 'x-api-key: api-key'
curl '{SubscribeURL}'
curl -X 'POST' 'https://api-rms.hostify.com/reservations/custom_field_update' -H 'accept: */*' -H 'x-api-key: api-key' -H 'Content-Type: application/json' -d '{"reservation_id": 0, "custom_field_id": 0, "value": "string"}'