"""HTTP entry point for opening maintenance chat rooms."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .infrai_realtime import InfraiError, InfraiRealtimeClient
from .maintenance_rooms import MaintenanceRoomCoordinator, OpenMaintenanceRoom, RoomOpened

app = FastAPI(title="Property maintenance chat")


@app.post("/maintenance/rooms", response_model=RoomOpened, status_code=201)
def open_maintenance_room(command: OpenMaintenanceRoom) -> RoomOpened:
    client = InfraiRealtimeClient()
    try:
        return MaintenanceRoomCoordinator(client).open(command)
    except InfraiError as exc:
        caller_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=caller_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    finally:
        client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("property_chat.service:app", host="127.0.0.1", port=8000)
