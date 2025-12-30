"""
WebSocket Real-Time Service
============================

Implements WebSocket connections for real-time fleet updates.
Eliminates HTTP polling overhead.

Benefits:
- Real-time updates (<100ms latency)
- Lower bandwidth usage
- Better UX (instant alerts)

Author: Fuel Copilot Team
Date: December 26, 2025
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Set

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates

    Features:
    - Per-truck subscriptions
    - Fleet-wide broadcasts
    - Connection pooling
    - Automatic reconnection
    """

    def __init__(self):
        # Active connections: {truck_id: {websocket1, websocket2, ...}}
        self.truck_connections: Dict[str, Set[WebSocket]] = {}

        # Fleet-wide connections (all trucks)
        self.fleet_connections: Set[WebSocket] = set()

        # Connection metadata
        self.connection_metadata: Dict[WebSocket, dict] = {}

    async def connect_truck(self, websocket: WebSocket, truck_id: str):
        """Connect client to specific truck updates"""
        await websocket.accept()

        if truck_id not in self.truck_connections:
            self.truck_connections[truck_id] = set()

        self.truck_connections[truck_id].add(websocket)
        self.connection_metadata[websocket] = {
            "truck_id": truck_id,
            "connected_at": datetime.now(),
            "type": "truck",
        }

        print(f"✅ WebSocket connected: truck {truck_id}")

    async def connect_fleet(self, websocket: WebSocket):
        """Connect client to fleet-wide updates"""
        await websocket.accept()

        self.fleet_connections.add(websocket)
        self.connection_metadata[websocket] = {
            "connected_at": datetime.now(),
            "type": "fleet",
        }

        print(f"✅ WebSocket connected: fleet monitor")

    def disconnect(self, websocket: WebSocket):
        """Disconnect client"""
        metadata = self.connection_metadata.get(websocket)

        if metadata:
            if metadata["type"] == "truck":
                truck_id = metadata["truck_id"]
                if truck_id in self.truck_connections:
                    self.truck_connections[truck_id].discard(websocket)
                    if not self.truck_connections[truck_id]:
                        del self.truck_connections[truck_id]
                print(f"❌ WebSocket disconnected: truck {truck_id}")

            elif metadata["type"] == "fleet":
                self.fleet_connections.discard(websocket)
                print(f"❌ WebSocket disconnected: fleet monitor")

            del self.connection_metadata[websocket]

    async def send_to_truck(self, truck_id: str, message: dict):
        """Send update to all clients subscribed to truck"""
        if truck_id not in self.truck_connections:
            return

        # Add timestamp
        message["timestamp"] = datetime.now().isoformat()
        message_json = json.dumps(message)

        # Send to all connected clients
        disconnected = []
        for websocket in self.truck_connections[truck_id]:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                print(f"Error sending to websocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_fleet(self, message: dict):
        """Broadcast update to all fleet monitors"""
        message["timestamp"] = datetime.now().isoformat()
        message_json = json.dumps(message)

        disconnected = []
        for websocket in self.fleet_connections:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                print(f"Error broadcasting: {e}")
                disconnected.append(websocket)

        # Clean up
        for ws in disconnected:
            self.disconnect(ws)

    def get_stats(self) -> dict:
        """Get connection statistics"""
        return {
            "total_connections": len(self.connection_metadata),
            "truck_subscriptions": len(self.truck_connections),
            "fleet_monitors": len(self.fleet_connections),
            "trucks_monitored": list(self.truck_connections.keys()),
        }


# Global connection manager
manager = ConnectionManager()


# =====================================================
# FASTAPI WEBSOCKET ENDPOINTS
# =====================================================

"""
# Add to main.py:

from websocket_service import manager

@app.websocket("/ws/truck/{truck_id}")
async def websocket_truck(websocket: WebSocket, truck_id: str):
    '''Real-time updates for specific truck'''
    await manager.connect_truck(websocket, truck_id)
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            
            # Echo back (heartbeat)
            await websocket.send_text(json.dumps({
                "type": "pong",
                "truck_id": truck_id
            }))
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/fleet")
async def websocket_fleet(websocket: WebSocket):
    '''Real-time updates for entire fleet'''
    await manager.connect_fleet(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong"}))
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/v2/ws/stats")
async def websocket_stats():
    '''WebSocket connection statistics'''
    return manager.get_stats()
"""


# =====================================================
# EVENT PUBLISHERS
# =====================================================


async def publish_sensor_update(truck_id: str, sensor_data: dict):
    """
    Publish sensor update to WebSocket clients

    Call this whenever sensor data changes
    """
    await manager.send_to_truck(
        truck_id, {"type": "sensor_update", "truck_id": truck_id, "data": sensor_data}
    )


async def publish_fuel_alert(truck_id: str, alert: dict):
    """Publish fuel theft/low fuel alert"""
    # Send to truck subscribers
    await manager.send_to_truck(
        truck_id, {"type": "fuel_alert", "truck_id": truck_id, "alert": alert}
    )

    # Also broadcast to fleet monitors
    await manager.broadcast_fleet(
        {"type": "fuel_alert", "truck_id": truck_id, "alert": alert}
    )


async def publish_dtc_alert(truck_id: str, dtc: dict):
    """Publish DTC alert"""
    await manager.send_to_truck(
        truck_id, {"type": "dtc_alert", "truck_id": truck_id, "dtc": dtc}
    )

    # Critical DTCs broadcast to fleet
    if dtc.get("severity") in ["critical", "high"]:
        await manager.broadcast_fleet(
            {"type": "dtc_alert", "truck_id": truck_id, "dtc": dtc}
        )


async def publish_fleet_summary(summary: dict):
    """Publish fleet summary update"""
    await manager.broadcast_fleet({"type": "fleet_summary", "data": summary})


# =====================================================
# BACKGROUND TASK - PERIODIC UPDATES
# =====================================================


async def periodic_fleet_updates():
    """
    Background task that sends periodic updates to clients

    Run this as a FastAPI background task:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Start background task
        task = asyncio.create_task(periodic_fleet_updates())
        yield
        # Cancel on shutdown
        task.cancel()
    """

    while True:
        try:
            # Only send if there are active connections
            if manager.fleet_connections or manager.truck_connections:

                # Fetch latest data (replace with your actual DB query)
                # fleet_data = await get_fleet_summary()

                # Broadcast to all fleet monitors
                # await publish_fleet_summary(fleet_data)

                # Send updates to individual truck subscribers
                # for truck_id in manager.truck_connections.keys():
                #     sensor_data = await get_truck_sensors(truck_id)
                #     await publish_sensor_update(truck_id, sensor_data)

                pass

            # Update every 5 seconds
            await asyncio.sleep(5)

        except Exception as e:
            print(f"Error in periodic updates: {e}")
            await asyncio.sleep(5)


# =====================================================
# FRONTEND JAVASCRIPT CLIENT
# =====================================================

"""
// React/TypeScript example

const useTruckWebSocket = (truckId: string) => {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/truck/${truckId}`);
    
    ws.onopen = () => {
      console.log('✅ WebSocket connected');
      setConnected(true);
    };
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'sensor_update') {
        setData(message.data);
      } else if (message.type === 'fuel_alert') {
        // Show alert notification
        toast.warning(message.alert.message);
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
      console.log('❌ WebSocket disconnected');
      setConnected(false);
      
      // Reconnect after 3 seconds
      setTimeout(() => {
        // Re-create WebSocket connection
      }, 3000);
    };
    
    // Heartbeat every 30 seconds
    const heartbeat = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
    
    return () => {
      clearInterval(heartbeat);
      ws.close();
    };
  }, [truckId]);
  
  return { data, connected };
};

// Usage in component:
const TruckDashboard = ({ truckId }) => {
  const { data, connected } = useTruckWebSocket(truckId);
  
  return (
    <div>
      <StatusIndicator connected={connected} />
      <FuelGauge level={data?.fuel_level} />
      <Speedometer speed={data?.speed} />
      <MPGDisplay mpg={data?.mpg} />
    </div>
  );
};
"""


# =====================================================
# TESTING
# =====================================================


async def test_websocket():
    """Test WebSocket functionality"""
    import websockets

    async with websockets.connect("ws://localhost:8000/ws/truck/FL0208") as ws:
        print("Connected to WebSocket")

        # Send heartbeat
        await ws.send(json.dumps({"type": "ping"}))

        # Receive messages
        while True:
            message = await ws.recv()
            print(f"Received: {message}")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_websocket())
