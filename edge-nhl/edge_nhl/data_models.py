from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

# A generic row for a stats table
@dataclass
class StatRow:
    stat_label: str
    player_value: Optional[float] = None
    league_average: Optional[float] = None
    percentile: Optional[float] = None
    tooltip: Optional[str] = None

# For the radar chart, note that sometimes the value label may be numeric or a string.
@dataclass
class RadarChartItem:
    axis_label: str
    value: float
    value_label: Any

@dataclass
class RadarChartData:
    config: Dict[str, Any] = field(default_factory=dict)
    data: List[RadarChartItem] = field(default_factory=list)

# The parsed data now includes the extra sections.
@dataclass
class ParsedEdgeData:
    overview_section: List[StatRow] = field(default_factory=list)
    skating_speed_section: List[StatRow] = field(default_factory=list)
    skating_distance_section: List[StatRow] = field(default_factory=list)
    shot_speed_section: List[StatRow] = field(default_factory=list)
    shot_location_section: List[Any] = field(default_factory=list)  # remains as a list (table rows or raw JSON)
    zonetime_section: List[StatRow] = field(default_factory=list)    # now a list of StatRow
    radar_chart: Optional[RadarChartData] = None