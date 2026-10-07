from datetime import datetime, timezone

from property_chat.maintenance_rooms import (
    InspectionReminder,
    MaintenanceRequest,
    OpenMaintenanceRoom,
    TenantDocument,
    build_event_plan,
)


def test_urgent_request_sets_attention_and_keeps_room_timeline_ordered() -> None:
    command = OpenMaintenanceRoom(
        maintenance=MaintenanceRequest(
            request_id="req-42",
            property_id="elm-court",
            tenant_id="tenant-7",
            summary="Water is entering the kitchen ceiling",
            priority="urgent",
        ),
        documents=[TenantDocument(document_id="photo-3", label="Ceiling photo")],
        inspection=InspectionReminder(
            inspection_id="inspect-9",
            due_at=datetime(2026, 9, 8, 2, 30, tzinfo=timezone.utc),
        ),
    )

    events = build_event_plan(command)

    assert [event.name for event in events] == [
        "maintenance.requested",
        "tenant.document_shared",
        "inspection.reminder_scheduled",
    ]
    assert events[0].data["attention"] == "immediate"
    assert events[2].data["due_at"] == "2026-09-08T02:30:00+00:00"
