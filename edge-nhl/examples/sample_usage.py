#!/usr/bin/env python3
import logging
import sys
import json
from dataclasses import asdict

from edge_nhl.selenium_cookie import get_nhl_edge_cookies
from edge_nhl.client import EdgeNHLClient

def main():
    # Configure logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    logger = logging.getLogger(__name__)

    # Retrieve cookies via Selenium
    cookies = get_nhl_edge_cookies(headless=True)

    # Initialize the client with cookies
    client = EdgeNHLClient(
        cookies=cookies,
        rate_limit_seconds=0.5,
        save_messages=False
    )

    # Specify a player_id and fetch the data
    player_id = "8478402"
    logger.info("Fetching parsed Edge data for player_id=%s...", player_id)
    parsed_data = client.fetch_player_data_sync(player_id)

    # For demonstration, print the zone time section if present
    if hasattr(parsed_data, "zonetime_section"):
        # If you store the zonetime section parsed output in an attribute (e.g., zonetime_section)
        logger.info("Zone Time Section Parsed Data: %s", parsed_data.zonetime_section)
    else:
        logger.info("No parsed zonetime section found.")

    # Convert full parsed data to a dict and save as JSON
    try:
        parsed_data_dict = asdict(parsed_data)
    except Exception as e:
        logger.error("Error converting parsed data to dict: %s", e)
        parsed_data_dict = {}

    output_filename = "parsed_output.json"
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(parsed_data_dict, f, indent=2)
        logger.info("Parsed data saved to %s", output_filename)
    except Exception as e:
        logger.error("Error saving parsed data to JSON file: %s", e)

if __name__ == "__main__":
    main()