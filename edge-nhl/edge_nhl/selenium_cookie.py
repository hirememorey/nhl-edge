import logging
import time
from typing import Dict

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

def get_nhl_edge_cookies(headless: bool = True) -> Dict[str, str]:
    """
    Launch a Selenium-controlled Chrome browser to navigate to edge.nhl.com and extract cookies.
    
    :param headless: Whether to run the browser in headless mode.
    :return: Dictionary of cookies.
    """
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        url = "https://edge.nhl.com/"
        logger.info("Navigating to %s to retrieve cookies.", url)
        driver.get(url)
        time.sleep(3)  # Wait for the page to load
        cookies_list = driver.get_cookies()
        logger.debug("Raw cookies list: %s", cookies_list)
        cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies_list}
        logger.info("Retrieved %d cookies from edge.nhl.com", len(cookie_dict))
    finally:
        driver.quit()

    return cookie_dict