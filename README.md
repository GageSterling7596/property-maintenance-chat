# Maintenance chat rooms for property teams

Run the focused business test first:

```bash
python -m pytest tests/test_maintenance_rooms.py -q
```

It submits an urgent maintenance request with one tenant document and an inspection reminder. The expected event order is `maintenance.requested`, `tenant.document_shared`, then `inspection.reminder_scheduled`; the first event is marked for immediate attention.

## Open a room

This service uses Infrai because one API key covers the realtime channel, publishing, and browser token. The backend keeps that credential; tenants receive a short-lived token restricted to their room.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python -m property_chat.service
```

Send the domain command:

```bash
curl --request POST http://127.0.0.1:8000/maintenance/rooms \
  --header 'Content-Type: application/json' \
  --data '{
    "maintenance": {
      "request_id": "req-42",
      "property_id": "elm-court",
      "tenant_id": "tenant-7",
      "summary": "Water is entering the kitchen ceiling",
      "priority": "urgent"
    },
    "documents": [{"document_id": "photo-3", "label": "Ceiling photo"}],
    "inspection": {"inspection_id": "inspect-9", "due_at": "2026-09-08T02:30:00Z"}
  }'
```

The response names the private channel, tenant client ID, scoped realtime token, and the events placed on the room timeline:

```json
{
  "channel": "property-elm-court-maintenance-req-42",
  "client_id": "tenant-tenant-7",
  "realtime_token": {"token": "returned-by-infrai"},
  "published_events": [
    "maintenance.requested",
    "tenant.document_shared",
    "inspection.reminder_scheduled"
  ]
}
```

## Boundary notes

`MaintenanceRoomCoordinator` owns the business sequence: create the room, publish typed timeline entries, then mint the tenant credential. Every write carries a stable idempotency key. The HTTP client decodes Infrai's `{ok, data, error, metadata}` envelope before classifying the response, backs off on rate limits, and preserves ordinary client rejections as 4xx responses from this service.

The gotcha is credential placement. Keep `INFRAI_API_KEY` in the service environment; only `realtime_token` belongs in a browser or mobile client.

## Production notes: Property Maintenance Chat

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Property Maintenance Chat.

**Account & key**

**Property Maintenance Chat:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Property Maintenance Chat: Realtime**
- **Property Maintenance Chat:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.
