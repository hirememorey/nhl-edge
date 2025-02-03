import json
import logging
from bs4 import BeautifulSoup
from html import unescape
from edge_nhl.data_models import ParsedEdgeData, StatRow, RadarChartData, RadarChartItem

logger = logging.getLogger(__name__)

def parse_html_content(html: str, target: str) -> ParsedEdgeData:
    parsed = ParsedEdgeData()  # all fields default to empty lists or None
    html = unescape(html)
    soup = BeautifulSoup(html, "lxml")
    
    if target == "#overview-section-content":
        parsed.overview_section = parse_table(soup)
        parsed.radar_chart = parse_radar_chart(soup)
        logger.debug(f"Parsed overview section: {len(parsed.overview_section)} rows, radar_chart exists: {parsed.radar_chart is not None}")
    elif target == "#skatingspeed-section-content":
        parsed.skating_speed_section = parse_table(soup)
        logger.debug(f"Parsed skating speed section: {len(parsed.skating_speed_section)} rows")
    elif target == "#skatingdistance-section-content":
        parsed.skating_distance_section = parse_table(soup)
        logger.debug(f"Parsed skating distance section: {len(parsed.skating_distance_section)} rows")
    elif target == "#shotspeed-section-content":
        parsed.shot_speed_section = parse_table(soup, columns=4, is_shot_speed=True)
        logger.debug(f"Parsed shot speed section: {len(parsed.shot_speed_section)} rows")
    elif target == "#shotlocation-section-content":
        shot_chart = soup.find("sl-webc-shot-chart")
        if shot_chart and shot_chart.has_attr("data-json"):
            try:
                data = json.loads(unescape(shot_chart["data-json"]))
                parsed.shot_location_section = data.get("chartData", [])
            except Exception as e:
                logger.error(f"Error parsing shot chart JSON: {e}")
                # Fall back to table parsing:
                parsed.shot_location_section = parse_table(soup, columns=4)
        else:
            parsed.shot_location_section = parse_table(soup, columns=4)
        logger.debug(f"Parsed shot location section: {len(parsed.shot_location_section)} rows")
    elif target == "#zonetime-section-content":
        parsed.zonetime_section = parse_zone_time_table(soup)
        logger.debug(f"Parsed zonetime section: {len(parsed.zonetime_section)} rows")
    else:
        logger.warning(f"Unknown target received: {target}")
    
    return parsed

def parse_zone_time_table(soup: BeautifulSoup) -> list:
    """
    Parse the zone‑time table in the zone‑time section.
    We only need the first two columns:
      - The stat label (e.g. "Offensive Zone")
      - The player value (e.g. "49.8%")
    Returns a list of StatRow objects.
    """
    rows_data = []
    # Use a specific selector to pick the table from the left column.
    table = soup.select_one("div.col-lg-6.col-md-6 div.table-responsive table.table-hover")
    if table:
        tbody = table.find("tbody")
        if tbody:
            rows = tbody.find_all("tr")
            logger.debug(f"Zone time table found with {len(rows)} rows")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    stat_label = cells[0].get_text(strip=True)
                    value_text = cells[1].get_text(strip=True)
                    player_value = convert_to_float(value_text)
                    rows_data.append(StatRow(
                        stat_label=stat_label,
                        player_value=player_value
                    ))
                else:
                    logger.debug("Zone time row skipped, not enough cells")
        else:
            logger.warning("No tbody found in zone time table.")
    else:
        logger.warning("No zone time table found with selector 'div.col-lg-6.col-md-6 div.table-responsive table.table-hover'")
    return rows_data

def parse_table(soup: BeautifulSoup, columns: int = 4, is_shot_speed: bool = False) -> list:
    rows_data = []
    table = soup.select_one("table.table-hover")
    if table:
        tbody = table.find("tbody")
        if tbody:
            rows = tbody.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= columns:
                    stat_label = cells[0].get_text(strip=True)
                    player_value = convert_to_float(cells[1].get_text(strip=True))
                    if columns == 4:
                        league_average = convert_to_float(cells[2].get_text(strip=True))
                        percentile_text = cells[3].get_text(strip=True)
                        percentile = safe_convert(percentile_text) if is_shot_speed else convert_to_float(percentile_text)
                    else:
                        league_average = None
                        percentile = None
                    tooltip = None
                    span = cells[1].find("span")
                    if span and span.has_attr("data-tooltip"):
                        tooltip = span["data-tooltip"]
                    
                    rows_data.append(StatRow(
                        stat_label=stat_label,
                        player_value=player_value,
                        league_average=league_average,
                        percentile=percentile,
                        tooltip=tooltip
                    ))
                else:
                    logger.debug(f"Row skipped, not enough cells: {[cell.get_text(strip=True) for cell in cells]}")
    else:
        logger.debug("No table with class 'table table-hover' found in the provided HTML snippet.")
    return rows_data

def parse_radar_chart(soup: BeautifulSoup) -> RadarChartData:
    chart_el = soup.find("sl-webc-radar-chart", id="overview-radarchart")
    if chart_el and chart_el.has_attr("data-json"):
        try:
            chart_data = json.loads(unescape(chart_el["data-json"]))
        except Exception as e:
            logger.error(f"Error parsing radar chart JSON: {e}")
            chart_data = {}
        if "chartData" in chart_data and chart_data["chartData"]:
            data_list = chart_data["chartData"][0].get("data", [])
            items = []
            for item in data_list:
                try:
                    value = float(item.get("value", 0))
                except ValueError:
                    value = 0.0
                value_label = item.get("valueLabel", "")
                items.append(RadarChartItem(
                    axis_label=item.get("axisLabel", ""),
                    value=value,
                    value_label=value_label
                ))
            return RadarChartData(config=chart_data.get("config", {}), data=items)
    return None

def convert_to_float(text: str):
    try:
        text = text.replace("%", "").replace(",", "").strip()
        return float(text)
    except ValueError:
        return None

def safe_convert(text: str):
    try:
        return float(text)
    except Exception:
        return None

def merge_parsed_data(existing: ParsedEdgeData, new: ParsedEdgeData) -> ParsedEdgeData:
    if new.overview_section:
        existing.overview_section = new.overview_section
    if new.skating_speed_section:
        existing.skating_speed_section = new.skating_speed_section
    if new.skating_distance_section:
        existing.skating_distance_section = new.skating_distance_section
    if new.shot_speed_section:
        existing.shot_speed_section = new.shot_speed_section
    if new.shot_location_section:
        existing.shot_location_section = new.shot_location_section
    if new.zonetime_section:
        existing.zonetime_section = new.zonetime_section
    if new.radar_chart:
        existing.radar_chart = new.radar_chart
    return existing