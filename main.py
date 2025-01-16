import os 
import pandas as pd 
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup 
from tenacity import retry, stop_after_attempt, wait_exponential 
import requests 
from logger import logger

# Creating folders
os.makedirs("output", exist_ok=True)
os.makedirs("downloaded_assets/images", exist_ok=True)

# Retry logic 
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8)) #a decorator
def fetch_page(playwright, url):
    try:
        browser = playwright.chromium.launch(headless=False) # If headless=True, the browser window will run in background not visible to me
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        return page, context, browser
    except Exception as e:
        logger.error(f"Error fetching page {url}: {e}")
        raise e

def handle_cookies(page):
    try:
        # Wait for the cookie popup to appear (if it exists)
        logger.info("Waiting for cookie consent popup...")
        cookie_button = page.locator("button:has-text('Accept')")
        if cookie_button.is_visible(timeout=30000):  # Wait up to 30 seconds
            cookie_button.click()
            logger.info("Cookie consent accepted.")
        else:
            logger.info("No cookie popup found. Proceeding...")
    except Exception as e:
        logger.error(f"Error handling cookies: {e}")

def scrape_data(page, part_number):
    try:
        page.wait_for_load_state("networkidle") #networkidle makes sure that the page is fully loaded before proceeding

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Locating data 
        description_label = soup.find("td", class_="productDetailsTable_DataLabel", string="Product Description")
        lifecycle_label = soup.find("td", class_="productDetailsTable_DataLabel", string="Product Lifecycle (PLM)")
        family_label = soup.find("td", class_="productDetailsTable_DataLabel", string="Product Family")
        effective_date_label = soup.find("td", class_="productDetailsTable_DataLabel", string="PLM Effective Date")
        notes_label = soup.find("td", class_="productDetailsTable_DataLabel", string="Notes")
        image_tag = soup.find("img", class_="productPicture")

        # Extracting data 
        description = description_label.find_next_sibling("td").text.strip() if description_label else None
        lifecycle = lifecycle_label.find_next_sibling("td").text.strip() if lifecycle_label else None
        product_family = family_label.find_next_sibling("td").text.strip() if family_label else None
        plm_effective_date = effective_date_label.find_next_sibling("td").text.strip() if effective_date_label else None
        notes = notes_label.find_next_sibling("td").text.strip() if notes_label else None

        # Downloading product image
        if image_tag and "src" in image_tag.attrs:
            image_url = image_tag["src"]
            image_path = f"downloaded_assets/images/{part_number}.jpg"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                "Referer": "https://mall.industry.siemens.com/",
            }
            try:
                response = requests.get(image_url, headers=headers, stream=True)
                if response.status_code == 200:
                    with open(image_path, "wb") as img_file:
                        for chunk in response.iter_content(1024):
                            img_file.write(chunk)
                    logger.info(f"Downloaded image for part number {part_number}.")
                else:
                    logger.warning(f"Failed to download image for part number {part_number}: HTTP {response.status_code}")
            except Exception as e:
                logger.error(f"Error downloading image for part number {part_number}: {e}")
        else:
            image_path = None

        # Return all extracted data
        return {
            "Article Number": part_number,
            "Product Description": description,
            "Product Family": product_family,
            "Product Lifecycle (PLM)": lifecycle,
            "PLM Effective Date": plm_effective_date,
            "Notes": notes,
            "Product Image": image_path,
        }

    except Exception as e:
        logger.error(f"Error scraping data for part number {part_number}: {e}")
        return None

def main():
    input_file = "input/sample_part_numbers.xlsx"  
    output_file = "output/product_info.xlsx"

    # Loading part numbers
    try:
        part_numbers = pd.read_excel(input_file)["items_partnumber"].dropna().tolist()
    except KeyError:
        logger.error(f"The column 'items_partnumber' does not exist in {input_file}.")
        return
    except Exception as e:
        logger.error(f"Error reading input file {input_file}: {e}")
        return

    all_data = []

    with sync_playwright() as playwright:
        for part_number in part_numbers:
            url = f"https://mall.industry.siemens.com/mall/en/vn/Catalog/Product/{part_number}"
            try:
                page, context, browser = fetch_page(playwright, url)
                handle_cookies(page)
                data = scrape_data(page, part_number)
                if data:
                    all_data.append(data)
                context.close()
                browser.close()
            except Exception as e:
                logger.error(f"Failed to scrape part number {part_number}: {e}")

    df = pd.DataFrame(all_data)
    df.to_excel(output_file, index=False)
    logger.info(f"Scraping completed. Data saved to {output_file}.")

if __name__ == "__main__":
    main()
