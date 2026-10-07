"""Domain decisions for a property maintenance room."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, model_validator

SafeId = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")

if TYPE_CHECKING:
    from .infrai_realtime import InfraiRealtimeClient


class MaintenanceRequest(BaseModel):
    request_id: str = SafeId
    property_id: str = SafeId
    tenant_id: str = SafeId
    summary: str = Field(min_length=3, max_length=240)
    priority: Literal["routine", "urgent"] = "routine"


class TenantDocument(BaseModel):
    document_id: str = SafeId
    label: str = Field(min_length=1, max_length=80)


class InspectionReminder(BaseModel):
    inspection_id: str = SafeId
    due_at: datetime

    @model_validator(mode="after")
    def require_timezone(self) -> "InspectionReminder":
        if self.due_at.tzinfo is None:
            raise ValueError("due_at must include a timezone")
        return self


class OpenMaintenanceRoom(BaseModel):
    maintenance: MaintenanceRequest
    documents: list[TenantDocument] = Field(default_factory=list, max_length=10)
    inspection: InspectionReminder | None = None


class RoomOpened(BaseModel):
    channel: str
    client_id: str
    realtime_token: dict[str, Any]
    published_events: list[str]


class PlannedEvent(BaseModel):
    name: str
    data: dict[str, Any]


def build_event_plan(command: OpenMaintenanceRoom) -> list[PlannedEvent]:
    request = command.maintenance
    attention = "immediate" if request.priority == "urgent" else "standard"
    events = [
        PlannedEvent(
            name="maintenance.requested",
            data={
                "request_id": request.request_id,
                "property_id": request.property_id,
                "tenant_id": request.tenant_id,
                "summary": request.summary,
                "priority": request.priority,
                "attention": attention,
            },
        )
    ]
    events.extend(
        PlannedEvent(
            name="tenant.document_shared",
            data={"document_id": document.document_id, "label": document.label},
        )
        for document in command.documents
    )
    if command.inspection:
        due_at = command.inspection.due_at.astimezone(timezone.utc).isoformat()
        events.append(
            PlannedEvent(
                name="inspection.reminder_scheduled",
                data={"inspection_id": command.inspection.inspection_id, "due_at": due_at},
            )
        )
    return events


class MaintenanceRoomCoordinator:
    def __init__(self, realtime: InfraiRealtimeClient) -> None:
        self._realtime = realtime

    def open(self, command: OpenMaintenanceRoom) -> RoomOpened:
        request = command.maintenance
        channel = _channel_name(request.property_id, request.request_id)
        self._realtime.create_channel(channel=channel, request_id=f"room:{request.request_id}")

        events = build_event_plan(command)
        for index, event in enumerate(events):
            self._realtime.publish(
                channel=channel,
                event=event.name,
                data=event.data,
                account_id=request.property_id,
                request_id=f"event:{request.request_id}:{index}",
            )

        client_id = f"tenant-{request.tenant_id}"
        token = self._realtime.issue_token(client_id=client_id, channel=channel)
        return RoomOpened(
            channel=channel,
            client_id=client_id,
            realtime_token=token,
            published_events=[event.name for event in events],
        )


def _channel_name(property_id: str, request_id: str) -> str:
    raw = f"property-{property_id}-maintenance-{request_id}"
    return re.sub(r"[^A-Za-z0-9_-]", "-", raw)
