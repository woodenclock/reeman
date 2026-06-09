"""Background WebSocket client for AXBot /ws/v2/topics."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

import streamlit as st
import websockets

WS_TOPICS_DEFAULT = [
    "/tracked_pose",
    "/battery_state",
    "/planning_state",
    "/wheel_state",
    "/slam/state",
    "/alerts",
]


class WebSocketManager:
    """Thread-safe topic store updated by a background WS loop."""

    def __init__(self, ws_url: str, topics: list[str] | None = None):
        self.ws_url = ws_url
        self.topics = list(topics or WS_TOPICS_DEFAULT)
        self._data: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws: Any | None = None
        self.connected = False
        self.last_error: str | None = None

    def get(self, topic: str) -> Any:
        with self._lock:
            return self._data.get(topic)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.connected = False

    def enable_topic(self, topic: str) -> None:
        with self._lock:
            if topic in self.topics:
                already = True
            else:
                self.topics.append(topic)
                already = False
        if already:
            return
        self._send_command({"enable_topic": [topic]})

    def disable_topic(self, topic: str) -> None:
        with self._lock:
            if topic not in self.topics:
                return
            self.topics.remove(topic)
            self._data.pop(topic, None)
        self._send_command({"disable_topic": [topic]})

    def _send_command(self, payload: dict) -> None:
        loop = self._loop
        ws = self._ws
        if not loop or not ws:
            return  # next reconnect will resync from self.topics
        try:
            fut = asyncio.run_coroutine_threadsafe(ws.send(json.dumps(payload)), loop)
            fut.result(timeout=2)
        except Exception:  # noqa: BLE001 — best effort; reconnect will resync
            pass

    def send_ws_message(self, payload: dict) -> None:
        """Outbound JSON (e.g. ``/follow_target_state`` publish). Uses same socket as topic control."""
        self._send_command(payload)

    def _set_topic(self, topic: str, payload: Any) -> None:
        with self._lock:
            self._data[topic] = payload

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._async_loop())
        finally:
            try:
                self._loop.close()
            finally:
                self._loop = None

    async def _async_loop(self) -> None:
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    self.connected = True
                    self.last_error = None
                    with self._lock:
                        topics_snapshot = list(self.topics)
                    if topics_snapshot:
                        await ws.send(json.dumps({"enable_topic": topics_snapshot}))
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = json.loads(raw)
                        topic = msg.get("topic")
                        if topic:
                            self._set_topic(topic, msg)
            except Exception as exc:  # noqa: BLE001 — reconnect loop
                self.connected = False
                self.last_error = str(exc)
                await asyncio.sleep(2)
            finally:
                self._ws = None


@st.cache_resource
def get_ws_manager(ws_url: str) -> WebSocketManager:
    return WebSocketManager(ws_url)


def ws_url_from_base(base_url: str) -> str:
    return base_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws/v2/topics"


def ensure_ws_running(base_url: str) -> WebSocketManager:
    manager = get_ws_manager(ws_url_from_base(base_url))
    manager.start()
    return manager


def stop_ws(base_url: str) -> None:
    try:
        manager = get_ws_manager(ws_url_from_base(base_url))
        manager.stop()
    except Exception:  # noqa: BLE001
        pass
    get_ws_manager.clear()


def get_ws_topic(topic: str, base_url: str | None = None) -> Any:
    url = ws_url_from_base(base_url) if base_url else ws_url_from_base(
        st.session_state.get("_ws_base_url", "http://127.0.0.1:8090")
    )
    return get_ws_manager(url).get(topic)
