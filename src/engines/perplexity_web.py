"""Perplexity-web Selenium engine — restored in phase 8.

Per-phrase web scraping over perplexity.ai using a guest session (no
login). A 900 ms sleep is inserted before each phrase so the host site
does not rate-limit the launcher subprocess. The legacy global-based
body is preserved verbatim; a thin :func:`translate` adapter binds the
required names from :class:`RuntimeContext` and returns ``(False, "")``
on any failure so the launcher pipe stays drained even when the
upstream UI breaks.
"""
from __future__ import annotations

import json
import time
import traceback
from time import sleep

import requests

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
)

from bs4 import BeautifulSoup

from runtime import RuntimeContext


INACTIVE = False
WEB_SLEEP_BETWEEN_PHRASES_SEC = 0.9   # 700-1200 ms range; midpoint chosen

__all__ = [
    "INACTIVE",
    "WEB_SLEEP_BETWEEN_PHRASES_SEC",
    "translate",
    "perplexity_close_messages",
    "selenium_chrome_perplexity_translate",
]


def translate(ctx: RuntimeContext, text: str) -> tuple[bool, str]:
    """Per-phrase translation entry point used by the active dispatcher.

    Sleeps :data:`WEB_SLEEP_BETWEEN_PHRASES_SEC` first, seeds the module
    globals the legacy body still reads, and delegates to
    :func:`selenium_chrome_perplexity_translate`. Any exception
    collapses to ``(False, "")`` so the block-loop continues with an
    empty translation rather than hanging.
    """
    time.sleep(WEB_SLEEP_BETWEEN_PHRASES_SEC)
    try:
        g = globals()
        g["driver"]         = ctx.browser.driver
        g["src_lang_name"]  = ctx.language.src_lang_name
        g["dest_lang_name"] = ctx.language.dest_lang_name
        g.setdefault("closed_cookies_accept_message_bool",  False)
        g.setdefault("close_install_extension_message_bool", False)
        g.setdefault("deepl_nb_clear_cached_times",          0)
        g.setdefault("engine_method",                        "web")
        g.setdefault("end_time",                             0.0)
        g.setdefault("elapsed_time",                         0.0)
        g.setdefault("json_configuration_array",             {})
        g.setdefault("logged_into_chatgpt",                  False)
        g.setdefault("bloc_number",                          1)
        g.setdefault("chrome_options",                       None)
        g.setdefault("service",                              None)
        return selenium_chrome_perplexity_translate(text, 2)
    except Exception as exc:
        print(f"[perplexity_web] translate failed: {exc}")
        return False, ""


# Names referenced inside the function bodies that historically came from the
# entry script's module globals. Importing this module does NOT bind them; the
# functions are preserved verbatim for future re-wiring.
#   driver, src_lang_name, dest_lang_name,
#   closed_cookies_accept_message_bool,
#   close_install_extension_message_bool,
#   deepl_nb_clear_cached_times, json_configuration_array,
#   end_time, elapsed_time, engine_method, logged_into_chatgpt,
#   chrome_options, bloc_number, service
# Helpers referenced from the active path:
#   safe_click, set_chrome_window_2_3_screen, deepl_close_messages,
#   build_translation_prompt, get_nested_value_from_json_array.


def perplexity_close_messages():
    """
    Closes all common Deepl popups, messages, and dialogs.
    No parameters needed.
    """
    global closed_cookies_accept_message_bool, close_install_extension_message_bool, driver
    
    close_install_extension_message_bool = False

    # List of XPaths/CSS selectors for popups/messages
    xpath_selectors = [
       "//*/text()[normalize-space(.)='Accept All Cookies']/parent::*"
    ]
    css_selectors = [
        "div.relative.w-full.overflow-hidden.rounded-lg",
        "button[data-testid='floating-signup-close-button']",
        "button[data-testid='floating-card-upsell-dismiss']"
    ]

    # Close elements by XPath
    for selector in xpath_selectors:
        try:
            el = WebDriverWait(driver, 0.01).until(EC.presence_of_element_located((By.XPATH, selector)))
            driver.execute_script("arguments[0].scrollIntoView();", el)
            safe_click(driver, el)
            # Mark cookies/extension as closed if relevant
            if "cookies" in selector.lower():
                closed_cookies_accept_message_bool = True
            if "w-6" in selector:
                close_install_extension_message_bool = True
        except Exception:
            continue

    # Close elements by CSS selector
    for selector in css_selectors:
        try:
            el = WebDriverWait(driver, 0.01).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            driver.execute_script("arguments[0].scrollIntoView();", el)
            safe_click(driver, el)
            close_install_extension_message_bool = True
        except Exception:
            continue
    
    if close_install_extension_message_bool:
        #Call another time in case some messages because layers order
        deepl_close_messages()


def selenium_chrome_perplexity_translate(to_translate, retry_count, max_try_count):
    global logged_into_chatgpt, src_lang_name, dest_lang_name, chrome_options, bloc_number, service, chrome_options
    
    translation = ""
    Translated = False
    # Progress bar to show only when deepl also shows it on the browser
    bar = None
    global closed_cookies_accept_message_bool, close_install_extension_message_bool, deepl_nb_clear_cached_times
    global engine_method, end_time, elapsed_time, json_configuration_array
    
    to_translate_phrases_array = to_translate.split("\n")
    to_translate_phrases_array_len = len(to_translate_phrases_array)
    
    if retry_count >= 1:
        print(f"Retrying perplexity translation : {retry_count}/{max_try_count} time")
        
    str_prompt = build_translation_prompt(src_lang_name, dest_lang_name, to_translate)
    
    #print(str_prompt)
    
    # Set variable to false if they are not globally defined
    try:
        tmp_var = closed_cookies_accept_message_bool
        tmp_var = close_install_extension_message_bool
    except Exception:
        closed_cookies_accept_message_bool = False
        close_install_extension_message_bool = False

    to_translate_phrases_array = to_translate.split("\n")
    to_translate_phrases_array_len = len(to_translate_phrases_array)

    set_chrome_window_2_3_screen()
    

    try:
        translation_page_openeing_loop_count = 4
        translation_page_opened = False
        
       # 1️ Open Google homepage
        driver.get("https://www.google.com/?hl=en&gl=us")

        # 2 Try to click "Accept all" if it exists
        try:
            wait = WebDriverWait(driver, 0.2)
            accept_button = wait.until(
                EC.presence_of_element_located((By.XPATH, "//div[normalize-space()='Accept all']/ancestor::button"))
            )
            wait.until(EC.element_to_be_clickable((By.XPATH, "//div[normalize-space()='Accept all']/ancestor::button")))
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", accept_button)
            
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
            
            consent_div = wait.until(
                EC.presence_of_element_located((By.XPATH, "//div[h1[text()='Before you continue to Google']]"))
            )
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", consent_div)
            
            safe_click(driver, accept_button)
            #print("✅ Clicked 'Accept all'")
        except TimeoutException:
            #print("ℹ️ 'Accept all' button not found, continuing...")
            pass

        # 3️ Open Google search results for 'perplexity ai'
        driver.get("https://www.google.com/search?q=perplexity+ai")

        # 4️ Try to find and click a link to perplexity.ai
        # Scroll into view first
        # wait for the link to appear
        try:
            perplexity_link = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='https://www.perplexity.ai/']"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", perplexity_link)
            # Optional small pause for smoothness
            time.sleep(0.2)
            # Click using JS for maximum reliability
            driver.execute_script("arguments[0].click();", perplexity_link)
        except Exception:
            pass
        
        current_url = driver.current_url
        if not current_url.startswith("https://perplexity.ai"):
            driver.get("https://www.perplexity.ai/")
        
        # Close "Try Comet brower" annoying layer
        try:
            # Locate the div by CSS selector
            div_element = driver.find_element(By.CSS_SELECTOR, "div.relative.w-full.overflow-hidden.rounded-lg")
            safe_click(driver, div_element)
            #print("Div clicked successfully.")
            # Send ESC to the <body>, not the div
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
            #print("ESC key sent to the page.")
        except NoSuchElementException:
            # Ignore if the element is not found
            pass
        
        # Locate the contenteditable div
        try:
            textarea = WebDriverWait(driver, 7).until(
                EC.presence_of_element_located((By.XPATH, "//*[@id='ask-input']"))
            )

            # Send text to the element
            safe_click(driver, textarea)
        except Exception:
            textarea = WebDriverWait(driver, 7).until(
                EC.presence_of_element_located((By.XPATH, "//*[@id='ask-input']"))
            )

            # Send text to the element
            safe_click(driver, textarea)
        
        # Assuming you already have a WebDriver instance (driver)
        #textarea = driver.find_element(By.ID, "ask-input")

        js_script = f"""
        const textarea = document.getElementById('ask-input');

        // Create a clipboard event with the desired text
        const clipboardData = new DataTransfer();
        clipboardData.setData('text/plain', `{str_prompt}`);
        const pasteEvent = new ClipboardEvent('paste', {{
          bubbles: true,
          cancelable: true,
          clipboardData: clipboardData
        }});

        // Focus and dispatch paste
        textarea.focus();
        textarea.dispatchEvent(pasteEvent);
        """

        driver.execute_script(js_script)
        
        
        #Click and close all annoyances messages
        perplexity_close_messages()

        #"""Click the floating card dismiss button if it exists."""
        try:
            # Wait until the button is present
            timeout=1
            button = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-testid='floating-card-upsell-dismiss']"))
            )
            
            # Scroll into view before clicking
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)

            # Try JS click (avoids intercepted click errors)
            driver.execute_script("arguments[0].click();", button)
            print("✅ Dismiss button clicked.")
        
        except TimeoutException:
            #print("❌ Dismiss button not found within timeout.")
            pass
        except WebDriverException as e:
            #print(f"⚠️ Click failed: {e}")
            pass
        
        perplexity_close_messages()
        
        submit_button = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.XPATH, '//button[@aria-label="Submit"]'))
        )
        safe_click(driver, submit_button)

        time.sleep(1)

        timeout = 300  # seconds
        poll_interval = 1  # seconds
        start_time = time.time()

       # print("⏳ Waiting for stop button to disappear", end='')
        while True:
            try:
                stop_button = driver.find_element(By.CSS_SELECTOR,  '[data-testid="stop-generating-response-button"]')
                if stop_button:
                    try:
                        if stop_button.is_displayed():
                            #print("⏳ Waiting for stop button to disappear...")
                            #print('.', end='')
                                        
                            # Sleep for 0.5 seconds before checking again
                            time.sleep(0.25)
                            # Locate the div by its class
                            try:
                                button = driver.find_element(By.CSS_SELECTOR, "button[data-testid='answer-mode-tabs-tab-search']")
                                safe_click(driver, button)

                                # Send PAGE_DOWN to the body (or active element)
                                #driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
                                driver.execute_script("window.scrollBy(0, window.innerHeight);")
                                #print("Button clicked and PAGE_DOWN sent")
                            except Exception:
                                try:
                                    #driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
                                    driver.execute_script("window.scrollBy(0, window.innerHeight);")
                                    #print("Button clicked and PAGE_DOWN sent")
                                except Exception:
                                    print("Cannot find html body...")
                                    pass
                                pass
                            #driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            
                            pass
                        else:
                            #print("\n✅ Stop button is no longer visible.")
                            #print("\n")
                            time.sleep(1)
                            break
                    except Exception:
                        break
                
            except NoSuchElementException:
                #print("✅ Stop button has been removed from the DOM.")
                #print("\n")
                break

            # Timeout check
            if time.time() - start_time > timeout:
                print("⚠️ Timed out waiting for stop button to disappear.")
                break

            time.sleep(poll_interval)
            
        time.sleep(1)

        input_nb_lines = len(to_translate.replace("\r", "").split("\n"))

        
        # Get the div with class "prose"
        try:
            prose_div = WebDriverWait(driver, 2.5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.prose"))
            )
        except Exception:
            pass

        try:
            button = driver.find_element(By.CSS_SELECTOR, "button[data-testid='answer-mode-tabs-tab-search']")
            safe_click(driver, button)

            # Send PAGE_DOWN to the body (or active element)
            #driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
            driver.execute_script("window.scrollBy(0, window.innerHeight);")
            #print("Button clicked and PAGE_DOWN sent")
        except Exception:
            try:
                #body = driver.find_element(By.TAG_NAME, "body")
                #body.send_keys(Keys.PAGE_DOWN)
                driver.execute_script("window.scrollBy(0, window.innerHeight);")
            except Exception:
                print("Cannot scroll down...")
                pass
                                
        # Try to get the div again (big)
        time.sleep(0.25)
        try:
            prose_div = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.prose"))
            )
        except Exception:
            pass
        
        # Extract all visible text content
        try:
            text = prose_div.text
        except Exception:
            driver.execute_script("window.focus();")
            text = ""

        # Split into lines (don't remove empties yet)
        result_lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Check for empty lines
        if any(line == "" for line in result_lines):
            print(f"Translation contains emtpy lines...")
            res = ""
        
        translated_phrases_array = result_lines
        if translated_phrases_array is None:
            translated_phrases_array_len = 0
        else:
            translated_phrases_array_len = len(translated_phrases_array)
        
        #print("result_lines:")
        #print(result_lines)
        
        res = None
                

        # for pos_remove in range(0,translated_phrases_array_len - to_translate_phrases_array_len):
        if translated_phrases_array_len >= to_translate_phrases_array_len:
            #print(f"input_nb_lines={input_nb_lines}")
            translated_phrases_array = translated_phrases_array[:input_nb_lines]
            #print("input_nb_lines: %s" % (input_nb_lines))
            #input("array: %s" % (translated_phrases_array))
            res = "\n".join(translated_phrases_array)
            if translated_phrases_array_len > to_translate_phrases_array_len + 1:
                print("Found %s lines out of %s lines" % (translated_phrases_array_len, to_translate_phrases_array_len))
                result_lines = []
                res = ""
            if any(line == "" for line in result_lines):
                print(f"Translation contains emtpy lines...")
                res = ""

        if translated_phrases_array_len < to_translate_phrases_array_len:
            res = ""
            print(f"Error, not enough lines : {translated_phrases_array_len} out of {to_translate_phrases_array_len} lines")
            print(f"Cleaning up perplexity cookies...")
            driver.delete_all_cookies()
            sleep(0.3)

        #print(res)
        
        ##################################################
        # Delete this chat from perplexity AI history
        try:
            wait = WebDriverWait(driver, 1)

            # 1. Click the three-dot (⋯) menu icon
            dots_button = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//button[@data-testid='thread-dropdown-menu']"
            )))
            safe_click(driver, dots_button)

            # 2. Click the Delete option (with trash icon and text "Delete")
            delete_button = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                '//div[contains(@class, "cursor-pointer")]//span[text()="Delete"]'
            )))
            safe_click(driver, delete_button)

            # Wait for the Confirm button and click it
            confirm_button = WebDriverWait(driver, 1).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="thread-delete-confirm"]'))
            )
            safe_click(driver, confirm_button)
        except Exception:
            print("Unable to delete conversation")
        
        # Close "Try Comet brower" annoying layer, ignore if the layer is not present
        try:
            # Locate the div by CSS selector
            div_element = driver.find_element(By.CSS_SELECTOR, "div.relative.w-full.overflow-hidden.rounded-lg")
            safe_click(driver, div_element)
            #print("Div clicked successfully.")
            # Send ESC to the <body>, not the div
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
            #print("ESC key sent to the page.")
        except NoSuchElementException:
            # Ignore if the element is not found
            pass
        
        translation = res  
    except Exception:
        var = traceback.format_exc()
        print(var)
        sleep(1)
        # sys.exit(0)
    if translation != "":
        return True, translation
    else:
        return False, translation

