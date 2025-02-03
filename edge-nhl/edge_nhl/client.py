import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import aiohttp
from aiohttp import WSMsgType

from edge_nhl.parsers import parse_html_content, merge_parsed_data
from edge_nhl.data_models import ParsedEdgeData

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Origin": "https://edge.nhl.com",
}


class EdgeNHLClient:
    def __init__(
        self,
        cookies: Optional[Dict[str, str]] = None,
        rate_limit_seconds: float = 1.0,
        save_messages: bool = False
    ):
        self._cookies = cookies or {}
        self._parsed_data = ParsedEdgeData()
        self.rate_limit_seconds = rate_limit_seconds
        self.save_messages = save_messages

        self.output_dir = Path("data")
        if self.save_messages:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        self.subsequent_sent = False

        # New: Track received and expected targets.
        self.received_targets = set()
        self.expected_targets = {
            "#overview-section-content",
            "#skatingspeed-section-content",
            "#skatingdistance-section-content",
            "#shotspeed-section-content",
            "#shotlocation-section-content",
            "#zonetime-section-content",
        }

    async def connect_and_communicate(self, player_id: str):
        ws_url = f"wss://edge.nhl.com/en/skater/{player_id}"
        logger.info("Connecting to %s", ws_url)
        headers = HEADERS.copy()
        if self._cookies:
            cookie_header = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
            headers["Cookie"] = cookie_header

        async with aiohttp.ClientSession(cookies=self._cookies) as session:
            async with session.ws_connect(
                ws_url,
                headers=headers,
                ssl=False,
                heartbeat=15,
                receive_timeout=20
            ) as ws:
                logger.info("WebSocket connected. Sending initial handshake.")
                await self._send_initial_message(ws, player_id)
                sub_msgs = self._generate_subsequent_messages(player_id)
                for idx, sub_msg in enumerate(sub_msgs, start=1):
                    logger.debug("Sending subsequent message %d: %s", idx, sub_msg)
                    await ws.send_json(sub_msg)
                    await asyncio.sleep(0.2)
                self.subsequent_sent = True

                async for msg in ws:
                    logger.debug("Received WS message: type=%s, data=%r",
                                 msg.type, getattr(msg, "data", None))
                    if msg.type == WSMsgType.TEXT:
                        await self._handle_text_message(msg.data, ws, player_id)
                    elif msg.type in (WSMsgType.CLOSED, WSMsgType.CLOSING):
                        logger.info("WebSocket closed by server.")
                        break
                    elif msg.type == WSMsgType.ERROR:
                        logger.error("WebSocket error: %s", msg)
                        break
                    await asyncio.sleep(self.rate_limit_seconds)
                logger.info("WebSocket connection closed.")

    async def _send_initial_message(self, ws, player_id: str):
        initial_msg = {
            "type": "action",
            "event": {
                "domain": "edge.nhl.com",
                "uri": f"/en/skater/{player_id}",
                "action": "getLabel",
                "data": {
                    "params": {
                        "type": "skaters",
                        "player": player_id,
                        "rootName": "skatersProfiles",
                        "source": "players"
                    }
                }
            }
        }
        await ws.send_json(initial_msg)
        logger.info("Sent initial handshake message: %s", initial_msg)

    async def _handle_text_message(
        self, data_str: str, ws: aiohttp.ClientWebSocketResponse, player_id: str
    ):
        if self.save_messages:
            self._save_raw_message(data_str)
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            logger.warning("Received non-JSON message: %s", data_str)
            return
        logger.debug("Parsed JSON message: %s", data)
        msg_type = data.get("type")
        if msg_type == "html":
            html_content = data.get("html", "")
            target = data.get("target", "").strip()
            logger.debug("Found HTML snippet. target=%r, length=%d", target, len(html_content))
            # Track expected targets and close connection if done.
            if target in self.expected_targets:
                self.received_targets.add(target)
                if self.expected_targets.issubset(self.received_targets):
                    logger.info("All expected segments received. Closing WebSocket.")
                    await ws.close()
                    return

            parsed_segment = parse_html_content(html_content, target)
            logger.debug(
                "Parsed segment: overview rows=%d, radar_chart exists=%s",
                len(parsed_segment.overview_section),
                parsed_segment.radar_chart is not None
            )
            self._merge_parsed_data(parsed_segment)
        else:
            logger.debug("Ignoring non-HTML message type: %s", msg_type)

    # --- MODIFICATION STARTS HERE ---
    def _merge_parsed_data(self, new_data: ParsedEdgeData):
        """Merge the newly parsed data into the existing parsed data using the merge function."""
        logger.debug("Merging new parsed data into existing parsed data.")
        self._parsed_data = merge_parsed_data(self._parsed_data, new_data)
    # --- MODIFICATION ENDS HERE ---

    def get_parsed_data(self) -> ParsedEdgeData:
        return self._parsed_data

    def reset_parsed_data(self):
        logger.debug("Resetting parsed data.")
        self._parsed_data = ParsedEdgeData()

    def fetch_player_data_sync(self, player_id: str) -> ParsedEdgeData:
        asyncio.run(self.connect_and_communicate(player_id))
        return self.get_parsed_data()

    def _generate_subsequent_messages(self, player_id: str) -> List[Dict[str, Any]]:
        base_params = {
            "type": "skaters",
            "player": player_id,
            "rootName": "skatersProfiles",
            "source": "players"
        }
        section_configs = [
            ("overview", "#overview-section-content", {}),
            ("skatingspeed", "#skatingspeed-section-content", {}),
            ("skatingdistance", "#skatingdistance-section-content", {"manpower": "all"}),
            ("shotspeed", "#shotspeed-section-content", {}),
            ("shotlocation", "#shotlocation-section-content", {"shootingmetrics": "shots", "shotlocation": "all"}),
            ("zonetime", "#zonetime-section-content", {"manpower": "all"}),
        ]
        return [
            *self._create_profile_messages(player_id, base_params),
            *self._create_section_messages(player_id, section_configs)
        ]

    def _create_profile_messages(self, player_id: str, base_params: Dict[str, Any]) -> List[Dict]:
        messages = []
        for render_func, target in [
            ("renderPlayerCard", "#profile-playercard"),
            ("renderProfilePlayerSection", "#profile-section")
        ]:
            msg = {
                "type": "action",
                "event": {
                    "domain": "edge.nhl.com",
                    "uri": f"/en/skater/{player_id}",
                    "action": "load",
                    "data": {
                        "renderFunction": render_func,
                        "target": target,
                        "params": base_params,
                        "callbackFunction": "initializeDataElements"
                    }
                }
            }
            messages.append(msg)
        return messages

    def _create_section_messages(self, player_id: str, section_configs: List) -> List[Dict]:
        messages = []
        for section_name, target, extra_params in section_configs:
            msg = {
                "type": "action",
                "event": {
                    "domain": "edge.nhl.com",
                    "uri": f"/en/skater/{player_id}",
                    "action": "load",
                    "data": {
                        "renderFunction": "renderProfileContent",
                        "target": target,
                        "params": {
                            "sectionName": section_name,
                            "units": "imperial",
                            "season": "20242025",
                            "stage": "regular",
                            "feed": "skatersProfiles",
                            "id": player_id,
                            **extra_params
                        },
                        "callbackFunction": "runClientFns"
                    }
                }
            }
            messages.append(msg)
        return messages

    def _save_raw_message(self, data_str: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"message_{timestamp}.json"
        filepath = self.output_dir / filename
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(data_str)
            logger.debug("Saved raw message to %s", filepath)
        except Exception as e:
            logger.warning("Error saving raw message to %s: %s", filepath, e)