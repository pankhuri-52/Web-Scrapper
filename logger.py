import logging 
import os

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/scraping_log.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# A logger instance
logger = logging.getLogger(__name__)
