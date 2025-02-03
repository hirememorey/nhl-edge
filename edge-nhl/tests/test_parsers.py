import pytest
import json
from edge_nhl.parsers import parse_html_content

def test_parse_html_content_basic():
    html_snippet = """
    <div id="overview-section-content">
        <table>
            <tr>
                <td>Top Skating Speed (mph)</td>
                <th><span data-tooltip="11/14/2024 @ OTT">22.91</span></th>
                <th>22.09</th>
                <th>84</th>
            </tr>
        </table>
        <sl-webc-radar-chart data-json='{
            "config":{"levels":4,"maxValue":100},
            "chartData":[{"data":[{
                "axisLabel":"Top Skating Speed (mph)",
                "value":84,
                "valueLabel":84
            }]}]
        }'></sl-webc-radar-chart>
    </div>
    """
    parsed_data = parse_html_content(html_snippet, "#overview-section-content")
    assert len(parsed_data.overview_section) == 1
    row = parsed_data.overview_section[0]
    assert row.stat_label == "Top Skating Speed (mph)"
    assert row.player_value == 22.91
    assert row.tooltip == "11/14/2024 @ OTT"
    assert row.league_average == 22.09
    assert row.percentile == 84

    assert parsed_data.radar_chart is not None
    assert parsed_data.radar_chart.config["levels"] == 4
    assert parsed_data.radar_chart.data[0].axis_label == "Top Skating Speed (mph)"
    assert parsed_data.radar_chart.data[0].value == 84