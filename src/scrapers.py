from typing import Union, List
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup, NavigableString
import pandas as pd
import sys
import codecs
import re
import json
import time
import os
import logging
from queue import Queue

sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class LinkedInScraper:
    """Scrape LinkedIn job listings with flexible filtering."""
    
    DISTANCE_MAP = {0: 0, 8: 5, 16: 10, 40: 25, 80: 50, 160: 100}
    DATE_MAP = {"past month": 2592000, "past week": 604800, "past 24 hours": 86400}
    EXP_LEVEL_MAP = {"internship": 1, "entry level": 2, "associate": 3, "mid-senior level": 4, "director": 5, "executive": 6}
    JOB_TYPE_MAP = {"full-time": "F", "part-time": "P", "contract": "C", "temporary": "T", "other": "O", "internship": "I"}
    
    def __init__(self,
                 keywords: str,
                 locations: Union[List[str], str],
                 distance_in_km: int = None,
                 date_posted: str = None,
                 exp_level: Union[List[str], str] = None,
                 job_type: Union[List[str], str] = None,
                 pages: int = 1,
                 stop_callback=None):

        self.keywords = keywords
        self.locations = locations if isinstance(locations, list) else [locations]
        self.distance = distance_in_km
        self.date_posted = date_posted
        self.exp_level = exp_level if isinstance(exp_level, list) else ([exp_level] if exp_level else None)
        self.job_type = job_type if isinstance(job_type, list) else ([job_type] if job_type else None)
        self.pages = pages
        self.driver = None
        self.total_jobs_scraped = 0
        self.stop_callback = stop_callback or (lambda: False)

        logger.info(f"Initializing scraper for keyword '{keywords}' in {len(self.locations)} location(s)")
        self._validate_input()
    
    def _validate_input(self):
        """Validate all input parameters."""
        errors = []
        
        if not isinstance(self.keywords, str):
            errors.append("Keywords must be string.")
        
        if not all(isinstance(loc, str) for loc in self.locations):
            errors.append("All locations must be strings.")
        
        if self.distance is not None and self.distance not in self.DISTANCE_MAP:
            errors.append(f"Distance must be one of: {list(self.DISTANCE_MAP.keys())}")
        
        if self.date_posted and self.date_posted.lower() not in self.DATE_MAP:
            errors.append(f"Date posted must be one of: {list(self.DATE_MAP.keys())}")
        
        if self.exp_level:
            invalid = [el for el in self.exp_level if el.lower() not in self.EXP_LEVEL_MAP]
            if invalid:
                errors.append(f"Invalid experience levels: {invalid}. Must be one of: {list(self.EXP_LEVEL_MAP.keys())}")
        
        if self.job_type:
            invalid = [jt for jt in self.job_type if jt.lower() not in self.JOB_TYPE_MAP]
            if invalid:
                errors.append(f"Invalid job types: {invalid}. Must be one of: {list(self.JOB_TYPE_MAP.keys())}")
        
        if errors:
            logger.error("Input validation failed:\n" + "\n".join(errors))
            raise ValueError("\n".join(errors))
        
        logger.info("Input validation passed")
    
    def _build_url(self, location: str) -> str:
        """Build LinkedIn search URL with filters."""
        params = [f"keywords={self.keywords}", f"location={location}"]
        
        if self.distance:
            params.append(f"distance={self.DISTANCE_MAP[self.distance]}")
        
        if self.date_posted:
            params.append(f"f_TPR=r{self.DATE_MAP[self.date_posted.lower()]}")
        
        if self.exp_level:
            exp_codes = ",".join(str(self.EXP_LEVEL_MAP[el.lower()]) for el in self.exp_level)
            params.append(f"f_E={exp_codes}")
        
        if self.job_type:
            job_codes = ",".join(self.JOB_TYPE_MAP[jt.lower()] for jt in self.job_type)
            params.append(f"f_JT={job_codes}")
        
        return "https://www.linkedin.com/jobs/search/?" + "&".join(params)
    
    def _load_cookies(self, filename='linkedin_cookies.json'):
        """Load cookies or perform manual login."""
        if not os.path.exists(filename):
            logger.info("No cookies found, initiating manual login...")
            self._login_manual(filename)
        
        try:
            with open(filename, 'r') as f:
                cookies = json.load(f)
            
            self.driver.get('https://www.linkedin.com')
            for cookie in cookies:
                try:
                    if 'expiry' in cookie:
                        cookie['expiry'] = int(cookie['expiry'])
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.debug(f"Skipped cookie {cookie.get('name')}: {e}")
            logger.info("Cookies loaded successfully")
        except Exception as e:
            logger.error(f"Loading cookies failed: {e}")
            raise RuntimeError(f"Loading cookies failed: {e}")
    
    def _save_cookies(self, filename='linkedin_cookies.json'):
        """Save current cookies to file."""
        with open(filename, 'w') as f:
            json.dump(self.driver.get_cookies(), f)
        logger.info(f"Cookies saved to {filename}")
    
    def _login_manual(self, filename='linkedin_cookies.json'):
        """Prompt manual login and save cookies."""
        self.driver.get('https://www.linkedin.com/login')
        logger.info("Please log in manually in the browser window (180 seconds timeout)")
        
        try:
            WebDriverWait(self.driver, 180).until(
                EC.presence_of_element_located((By.XPATH, '//a[contains(@href, "/me/")]'))
            )
            logger.info("Login successful!")
            self._save_cookies(filename)
        except:
            logger.error("Login timeout exceeded (180s)")
            raise TimeoutError("Login timeout exceeded (180s)")
    
    def _scrape_page(self, jobs_data: Union[Queue,List[dict]], location: str, page_num: int):
        """Extract job listings from current page."""
        
        # wait until the page is loaded and check how many jobs there are.
        WebDriverWait(self.driver, 100).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'li.scaffold-layout__list-item'))
        )
        time.sleep(1)
        items = self.driver.find_elements(By.CSS_SELECTOR, 'li.scaffold-layout__list-item')
        logger.info(f"[{location}] Page {page_num}: Found {len(items)} job listings")
        
        # Scroll to bottom of job list to load all lazy-loaded items
        # This ensures all jobs are in the DOM before we start clicking
        job_list_container = self.driver.find_element(By.CSS_SELECTOR, 'li.scaffold-layout__list-item')
        self.driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", job_list_container)
        time.sleep(1)  # Wait for any lazy-loaded items to appear
   
        # check what data type job_data has
        is_list = True if type(jobs_data) == list else False
        old_title = None
        # loop for all job postiongs
        for idx, item in enumerate(items, 1):
            
            # Check if stop was requested
            if self.stop_callback():
                logger.info("Scraping stopped by user request")
                return

            try:
                # Close warning dialogs
                try:
                    if self.driver.find_element(By.XPATH, "//div[contains(@class, 'job-trust-pre-apply')]"):
                        close_button = self.driver.find_element(By.XPATH, "//button[1]")
                        close_button.click()
                except:
                    pass
                
                if idx != 1: 
                    WebDriverWait(self.driver, 5).until(
                        lambda driver: driver.find_element(By.CSS_SELECTOR, 'h1.t-24').text == old_title
                    )
                    item.click()
                    time.sleep(0.1)
                    item.click()
                    WebDriverWait(self.driver, 5).until(
                        lambda driver: driver.find_element(By.CSS_SELECTOR, 'h1.t-24').text != old_title
                    )
                    

                page_soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                company_div = page_soup.find('div', class_=re.compile(r'company-name'))
                company_link = company_div.find('a') if company_div else None
                company_text = company_link.get_text(strip=True) if company_link else "Not Available"

                try:
                    location_elem = self.driver.find_element(By.XPATH, "//span[contains(@dir, 'ltr')]/span[contains(@class,'tvm__text')][1]")
                    location_text = location_elem.text
                except:
                    location_text = "Not Available"

                title_elem = page_soup.find('h1', class_=re.compile(r't-24'))
                job_title = title_elem.get_text(strip=True) if title_elem else "Not Available"

                def _clean_description(element):
                    text_output = []
                    
                    if isinstance(element, NavigableString): return element
                    # Iterate over the children of the current element
                    for child in element.contents:
                        if isinstance(child, NavigableString):
                            text_output.append(child.strip())
                        elif child.name:
                            if child.name == 'li':
                                text_output.append(f"\n• {child.get_text(strip=True)}")
                            else:
                                text_output.append(_clean_description(child))
                    return " ".join(filter(None, text_output)).strip()
                        
                desc_elem = page_soup.find('div', class_=re.compile(r'jobs-description-content__text'))
                description = "\n".join([_clean_description(main_el) for main_el in desc_elem]).strip() if desc_elem else "Not Available"
                app_link = self._get_application_link()
                
                # we id jobs through their application links. If they are not found we cannot use it
                if app_link is None: continue
                
                data = {
                        'title': job_title,
                        'company': company_text,
                        'location': location_text,
                        'description': description,
                        'application_link': app_link
                }
                if is_list:
                    jobs_data.append(data)
                else:
                    # Putting into queue
                    jobs_data.put(data)
                    logger.info(f"[{location}] Job {idx}/{len(items)}: {job_title} @ {company_text} (queue size: ~{jobs_data.qsize()})")

                self.total_jobs_scraped += 1
                old_title = job_title
                
            except Exception as e:
                logger.warning(f"[{location}] Failed to scrape job {idx}/{len(items)}: {e}")
                continue
    
    def _get_application_link(self) -> str:
        """Extract application link from job posting."""
        try: 
            if self.driver.find_element(By.XPATH, "//button[contains(@aria-label,'Easy Apply to')][1]"): 
                time.sleep(0.5)
                return self.driver.current_url
        except: 
            pass 
        
        try:
            apply_button = self.driver.find_element(By.XPATH, "//button[contains(@id,'jobs-apply-button-id')][1]")
            apply_button.click()
            time.sleep(0.4)
            
            self.driver.switch_to.window(self.driver.window_handles[1])
            link = self.driver.current_url
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            return link
        except:
            return "Not Available"
    
    def scrape_jobs(self, queue:Queue=None) -> Union[None,pd.DataFrame]:
        """Scrape jobs across all specified locations and pages. If a queue is given all results are directly 
        written into the queue and nothing is returned. Otherwise a pandas DataFrame will be returned."""
        logger.info("=" * 60)
        logger.info("Starting LinkedIn job scraping")
        logger.info("=" * 60)

        opts = webdriver.ChromeOptions()
        opts.add_argument('--disable-blink-features=AutomationControlled')
        opts.add_experimental_option('excludeSwitches', ['enable-automation'])
        opts.add_experimental_option('useAutomationExtension', False)
        opts.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        self.driver = webdriver.Remote(
            command_executor='http://selenium:4444/wd/hub',
            options=opts
        )

        try:
            self._load_cookies()

            jobs_data = [] if not queue else queue

            for loc_idx, location in enumerate(self.locations, 1):
                # Check if stop was requested
                if self.stop_callback():
                    logger.info("Scraping stopped by user request")
                    break

                logger.info(f"Scraping location {loc_idx}/{len(self.locations)}: {location}")
                self.driver.get(self._build_url(location))

                page_num = 1
                while page_num <= self.pages:
                    # Check if stop was requested
                    if self.stop_callback():
                        logger.info("Scraping stopped by user request")
                        break

                    try:
                        self._scrape_page(jobs_data, location, page_num)

                        next_btn = self.driver.find_element(By.XPATH, "//button[span[text()='Next']]")
                        if not next_btn.is_enabled():
                            logger.info(f"[{location}] No more pages available")
                            break
                        next_btn.click()
                        time.sleep(2)
                        page_num += 1
                    except Exception as e:
                        logger.warning(f"[{location}] Error on page {page_num}: {e}")
                        break

                # Check if stop was requested before moving to next location
                if self.stop_callback():
                    logger.info("Scraping stopped by user request")
                    break

                logger.info(f"Completed {location} - Total jobs scraped so far: {self.total_jobs_scraped}\n")

            logger.info("=" * 60)
            logger.info(f"Scraping complete! Total jobs scraped: {self.total_jobs_scraped}")
            logger.info("=" * 60)
                
            if type(jobs_data) == list: 
                df = pd.DataFrame(jobs_data)
                prev_len = len(df)
                df.drop_duplicates(subset=["company", "title"], inplace=True)
                logger.info(f"{prev_len-len(df)} duplicate instances was/were detected and deleted.")

                return df

        except Exception as e:
            logger.error(f"LinkedIn scraping failed: {e}")
            raise RuntimeError(f"LinkedIn scraping failed with exception {e}")

        finally:
            self.driver.quit()
            logger.info("Browser closed")
            
# class LinkedInScraper:
#     """Scrape LinkedIn job listings with flexible filtering."""
    
#     DISTANCE_MAP = {0: 0, 8: 5, 16: 10, 40: 25, 80: 50, 160: 100}
#     DATE_MAP = {"past month": 2592000, "past week": 604800, "past 24 hours": 86400}
#     EXP_LEVEL_MAP = {"internship": 1, "entry level": 2, "associate": 3, "mid-senior level": 4, "director": 5, "executive": 6}
#     JOB_TYPE_MAP = {"full-time": "F", "part-time": "P", "contract": "C", "temporary": "T", "other": "O", "internship": "I"}
    
#     def __init__(self,
#                  keywords: str,
#                  locations: Union[List[str], str],
#                  distance_in_km: int = None,
#                  date_posted: str = None,
#                  exp_level: Union[List[str], str] = None,
#                  job_type: Union[List[str], str] = None,
#                  max_jobs: int = 50,
#                  stop_callback=None):

#         self.keywords = keywords
#         self.locations = locations if isinstance(locations, list) else [locations]
#         self.distance = distance_in_km
#         self.date_posted = date_posted
#         self.exp_level = exp_level if isinstance(exp_level, list) else ([exp_level] if exp_level else None)
#         self.job_type = job_type if isinstance(job_type, list) else ([job_type] if job_type else None)
#         self.max_jobs = max_jobs
#         self.driver = None
#         self.total_jobs_scraped = 0
#         self.stop_callback = stop_callback or (lambda: False)

#         logger.info(f"Initializing scraper for keyword '{keywords}' in {len(self.locations)} location(s)")
#         self._validate_input()
    
    
#     def _validate_input(self):
#         """Validate all input parameters."""
#         errors = []
        
#         if not isinstance(self.keywords, str):
#             errors.append("Keywords must be string.")
        
#         if not all(isinstance(loc, str) for loc in self.locations):
#             errors.append("All locations must be strings.")
        
#         if self.distance is not None and self.distance not in self.DISTANCE_MAP:
#             errors.append(f"Distance must be one of: {list(self.DISTANCE_MAP.keys())}")
        
#         if self.date_posted and self.date_posted.lower() not in self.DATE_MAP:
#             errors.append(f"Date posted must be one of: {list(self.DATE_MAP.keys())}")
        
#         if self.exp_level:
#             invalid = [el for el in self.exp_level if el.lower() not in self.EXP_LEVEL_MAP]
#             if invalid:
#                 errors.append(f"Invalid experience levels: {invalid}. Must be one of: {list(self.EXP_LEVEL_MAP.keys())}")
        
#         if self.job_type:
#             invalid = [jt for jt in self.job_type if jt.lower() not in self.JOB_TYPE_MAP]
#             if invalid:
#                 errors.append(f"Invalid job types: {invalid}. Must be one of: {list(self.JOB_TYPE_MAP.keys())}")
        
#         if errors:
#             logger.error("Input validation failed:\n" + "\n".join(errors))
#             raise ValueError("\n".join(errors))
        
#         logger.info("Input validation passed")
    
    
#     def _build_url(self, location: str) -> str:
#         """Build LinkedIn search URL with filters."""
#         params = [f"keywords={self.keywords}", f"location={location}"]
        
#         if self.distance:
#             params.append(f"distance={self.DISTANCE_MAP[self.distance]}")
        
#         if self.date_posted:
#             params.append(f"f_TPR=r{self.DATE_MAP[self.date_posted.lower()]}")
        
#         if self.exp_level:
#             exp_codes = ",".join(str(self.EXP_LEVEL_MAP[el.lower()]) for el in self.exp_level)
#             params.append(f"f_E={exp_codes}")
        
#         if self.job_type:
#             job_codes = ",".join(self.JOB_TYPE_MAP[jt.lower()] for jt in self.job_type)
#             params.append(f"f_JT={job_codes}")
        
#         return "https://www.linkedin.com/jobs/search/?" + "&".join(params) + "&position=1&pageNum=0"
    
#     def _close_pop_up(self) -> None: 
#         try: 
#             dismiss_button = self.driver.find_element(By.XPATH, "//button[@aria-label='Dismiss']")
#             self.driver.find_element("tag name", "body").send_keys(Keys.ESCAPE)
#         except:
#             pass 
#         return 
    
#     def _get_application_link(self) -> str:
#         """Extract application link from job posting."""
#         try: 
#             if self.driver.find_element(By.XPATH, "//button[contains(@aria-label,'Easy Apply to')][1]"): 
#                 time.sleep(0.5)
#                 return self.driver.current_url
#         except: 
#             pass 
        
#         try:
#             apply_button = self.driver.find_element(By.XPATH, "//div[contains(@class,'top-card-layout')]/button[contains(@class,'sign-up')]")
#             apply_button.click()
#         except:
#             pass 
#         try: 
#             apply_button = self.driver.find_element(By.XPATH, "//div[contains(@class,'top-card-layout')]/button[contains(@class,'apply-button')]")
#             apply_button.click()
#             time.sleep(0.4)
#             self._close_pop_up()
            
#             self.driver.switch_to.window(self.driver.window_handles[1])
#             link = self.driver.current_url
#             self.driver.close()
#             self.driver.switch_to.window(self.driver.window_handles[0])
#             return link
#         except:
#             return "Not Available"
    
    
#     def _extract_job_info(self):
#         """Extract job listings from current page."""
        
#         try:
#             if self.driver.find_element(By.XPATH, "//div[contains(@class, 'job-trust-pre-apply')]"):
#                 close_button = self.driver.find_element(By.XPATH, "//button[1]")
#                 close_button.click()
#         except:
#             pass
        
#         #click the show more button
#         self.driver.find_element(By.XPATH, "//button[@aria-label='Show more']").click()     
#         time.sleep(0.3)
#         # beautiful soup to extract the html - Find the data within
#         page_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
#         job_title = page_soup.find_all("div", class_=re.compile("entity-info"))[1].find("h2").get_text(strip=True)
#         company = page_soup.find_all("div", class_=re.compile("entity-info"))[1].find("h4").find("a").get_text().strip()
#         location = page_soup.find_all("div", class_=re.compile("entity-info"))[1].find("h4").find("div").find_all("span")[-1].get_text(strip=True)
        
#         def _clean_description(element):
#             text_output = []
            
#             if isinstance(element, NavigableString): return element
#             # Iterate over the children of the current element
#             for child in element.contents:
#                 if isinstance(child, NavigableString):
#                     text_output.append(child.strip())
#                 elif child.name:
#                     if child.name == 'li':
#                         text_output.append(f"\n• {child.get_text(strip=True)}")
#                     else:
#                         text_output.append(_clean_description(child))
#             return " ".join(filter(None, text_output)).strip()
                
#         description_el = page_soup.find('div', class_=re.compile("show-more"))
#         description = "\n".join([_clean_description(main_el) for main_el in description_el]).strip()
        
#         app_link = self._get_application_link()
                
#         # we id jobs through their application links. If they are not found we cannot use it
#         if app_link is None: return None
                
#         data = {
#             'title': job_title,
#             'company': company,
#             'location': location,
#             'description': description,
#             'application_link': app_link
#         }
#         return data
            
            
#     def _get_all_positions(self, jobs_data, location):
        
#         # bool for handling the data
#         is_list = True if type(jobs_data) == list else False
        
#         # init old_title to be able to track changes
#         old_title = None
#         j = 0
#         # Start running over the positions until the number of jobs is reached
#         # There are break statements in the loop if there are no further positions
#         # The scraping can also be interupted via the callback function.
#         while j <= self.max_jobs:
#             # Check if stop was requested
#             if self.stop_callback():
#                 logger.info("Scraping stopped by user request")
#                 break
#             try:
#                 # linkedin does lazy loading os always refresh the positions
#                 positions = self.driver.find_elements(By.XPATH, "//li/div[contains(@class, 'base-card')]")
#                 #Stop scraping if we cannot find more positions 
#                 if len(positions) <= j: break
                    
#                 #wait for linkedin to load. First one has to be skipped
#                 # if j != 0:
#                 #     WebDriverWait(self.driver, 5).until(
#                 #         lambda driver: driver.find_element(By.CSS_SELECTOR, 'h1.t-24').text == old_title
#                 #     )
#                 # after it has loaded we can go to the next position
#                 time.sleep(0.2)
#                 positions[self.total_jobs_scraped].click()
#                 # #again wait until the new title is there
#                 # WebDriverWait(self.driver, 5).until(
#                 #     lambda driver: driver.find_element(By.CSS_SELECTOR, 'h1.t-24').text != old_title
#                 # )
                
#                 # job card should now be open
#                 try: 
#                     data = self._extract_job_info()
#                 except Exception as e:
#                     logger.info(f"[{location}]: Failed to extract information about Job {self.total_jobs_scraped} inner loop {j}") 
                
#                 # data is None if the application link could not be found
#                 # since the application links are our unique identifier, we cannot use this job.
#                 if data == None: continue
#                 # Otherwise data is valid
#                 j += 1
#                 self.total_jobs_scraped += 1
#                 # Store data 
#                 if is_list:
#                     jobs_data.append(data)
#                     print(f"[{location}] Job {j}/{self.max_jobs}: {data['title']} @ {data['company']}")
#                 else:
#                     # Putting into queue
#                     jobs_data.put(data)
#                     logger.info(f"[{location}] Job {j}/{self.max_jobs}: {data['title']} @ {data['company']} (queue size: ~{jobs_data.qsize()})")
                
                
#                 # next_btn = self.driver.find_element(By.XPATH, "//button[span[text()='Next']]")
#                 # if not next_btn.is_enabled():
#                 #     logger.info(f"[{location}] No more pages available")
#                 #     break
#                 # next_btn.click()
#                 # time.sleep(2)
#                 # page_num += 1
#             except Exception as e:
#                 logger.warning(f"[{location}] Error in scrape_jobs while iterating through elements: {e}")
#                 break
    
#     def scrape_jobs(self, queue:Queue=None) -> Union[None,pd.DataFrame]:
#         """Scrape jobs across all specified locations and pages. If a queue is given all results are directly 
#         written into the queue and nothing is returned. Otherwise a pandas DataFrame will be returned."""
#         logger.info("=" * 60)
#         logger.info("Starting LinkedIn job scraping")
#         logger.info("=" * 60)

#         opts = webdriver.ChromeOptions()
#         opts.add_argument('--disable-blink-features=AutomationControlled')
#         opts.add_experimental_option('excludeSwitches', ['enable-automation'])
#         opts.add_experimental_option('useAutomationExtension', False)
#         opts.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
#         opts.add_argument("--start-maximized")  
#         self.driver = webdriver.Remote(
#             command_executor='http://selenium:4444/wd/hub',
#             options=opts
#         )

#         try:
#             # depending on if a queue is provided we write the job_data into queue or use a list
#             jobs_data = [] if not queue else queue

#             # looping over all locations
#             # wrapping the actual scraping function
#             for loc_idx, location in enumerate(self.locations, 1):
                
#                 # Check if stop was requested
#                 if self.stop_callback():
#                     logger.info("Scraping stopped by user request")
#                     break

#                 logger.info(f"Scraping location {loc_idx}/{len(self.locations)}: {location}")
#                 self.driver.get(self._build_url(location))

#                 self._close_pop_up()
#                 time.sleep(1)
#                 #close data privacy banner
#                 try:
#                     self.driver.find_element(By.XPATH, "//button[normalize-space()='Reject']").click()
#                 except: 
#                     pass
#                 time.sleep(0.5)
#                 # Reloading opens the first job
#                 self.driver.get(self._build_url(location))
                
#                 #start the actual scraping
#                 self._get_all_positions(jobs_data, location)
                
#                 # Check if stop was requested before moving to next location
#                 if self.stop_callback():
#                     logger.info("Scraping stopped by user request")
#                     break

#                 logger.info(f"Completed {location} - Total jobs scraped so far: {self.total_jobs_scraped}\n")

#             logger.info("=" * 60)
#             logger.info(f"Scraping complete! Total jobs scraped: {self.total_jobs_scraped}")
#             logger.info("=" * 60)
                
#             if type(jobs_data) == list: 
#                 df = pd.DataFrame(jobs_data)
#                 prev_len = len(df)
#                 df.drop_duplicates(subset=["company", "title"], inplace=True)
#                 logger.info(f"{prev_len-len(df)} duplicate instances was/were detected and deleted.")

#                 return df

#         except Exception as e:
#             logger.error(f"LinkedIn scraping failed: {e}")
#             raise RuntimeError(f"LinkedIn scraping failed with exception {e}")

#         finally:
#             self.driver.quit()
#             logger.info("Browser closed")
            
            
# if __name__ == "__main__": 
#     import debugpy
#     debugpy.listen(("0.0.0.0", 5678))
#     print("⏳ Debugger listening on port 5678...")
#     # Uncomment to make app wait for debugger before continuing:
#     debugpy.wait_for_client()
#     print("✅ Ready for debugger attachment")

#     scraper = LinkedInScraper("AI", "Munich", 8, "past week",max_jobs=100)
#     scraper.scrape_jobs()
    