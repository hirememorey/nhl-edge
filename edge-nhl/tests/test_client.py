import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
from aiohttp import WSMsgType

from edge_nhl.client import EdgeNHLClient

@pytest.mark.asyncio
async def test_client_connect_and_communicate():
    client = EdgeNHLClient(rate_limit_seconds=0)

    # The HTML snippet we want the parser to handle
    html_snippet = """
        <div id="overview-section-content">
            <table>
                <tr>
                    <td>Shots on Goal</td>
                    <th>100</th>
                    <th>50</th>
                    <th>80</th>
                </tr>
            </table>
        </div>
    """

    # Our JSON message
    html_message = {
        "type": "html",
        "target": "#overview-section-content",
        "html": html_snippet
    }
    mock_msg_data = json.dumps(html_message)

    # Create MagicMock messages for TEXT and CLOSED
    text_msg = MagicMock()
    text_msg.type = WSMsgType.TEXT
    text_msg.data = mock_msg_data

    closed_msg = MagicMock()
    closed_msg.type = WSMsgType.CLOSED

    # Mock WebSocket that yields the text and closed messages
    mock_ws = AsyncMock()
    mock_ws.__aiter__.return_value = [text_msg, closed_msg]

    # Patching so that:
    # 1) ws_connect(...) -> a mock context
    # 2) That context's __aenter__() returns mock_ws
    with patch("aiohttp.ClientSession.ws_connect") as mock_connect:
        mock_connect.return_value.__aenter__.return_value = mock_ws
        await client.connect_and_communicate("8478402")

    parsed_data = client.get_parsed_data()

    assert len(parsed_data.overview_section) == 1, "Expected 1 row, got 0"
    row = parsed_data.overview_section[0]
    assert row.stat_label == "Shots on Goal"
    assert row.player_value == 100.0
    assert row.league_average == 50.0
    assert row.percentile == 80