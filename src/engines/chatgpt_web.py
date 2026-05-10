"""ChatGPT-web Selenium engine — restored in phase 8.

Block-mode web scraping over chatgpt.com using a guest session (no
login). The legacy global-based body is preserved verbatim; a thin
:func:`translate` adapter binds the required names from
:class:`RuntimeContext` and returns ``(False, "")`` on any failure so
the launcher pipe stays drained even when the upstream UI breaks.

Timing
------
The 0.9 s pre-sleep introduced in phase 8 was a defensive guard added
before we ran a real-traffic test; the legacy code has no such sleep
because each call's ``delete_all_cookies()`` + ``driver.get()`` is
the de-facto throttle. The sleep is now ``0.0`` (legacy parity) —
:data:`engines._timing.CHATGPT_WEB_PRE_SLEEP`.
"""
from __future__ import annotations

import time
import traceback
from time import sleep

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    JavascriptException,
    TimeoutException,
    WebDriverException,
)

from bs4 import BeautifulSoup

from runtime import RuntimeContext
from selenium_utils import safe_click, set_chrome_window_2_3_screen
from config import get_nested_value_from_json_array
from engines._prompts import build_translation_prompt
from engines._timing import (
    CHATGPT_WEB_PRE_SLEEP,
    CHATGPT_WEB_LOGGED_OUT_LINK_WAIT,
    CHATGPT_WEB_STAY_LOGGED_OUT_WAIT,
    CHATGPT_WEB_AFTER_INJECT_SLEEP,
    CHATGPT_WEB_STREAMING_POLL,
    CHATGPT_WEB_MAX_STREAMING_WAIT,
)


INACTIVE = False
# Legacy parity: zero pre-sleep. See ``engines._timing`` for the reasoning
# trail. Kept as a module-level alias so external code that imported it
# during phase 8 keeps working — but the value is now 0.0.
WEB_SLEEP_BETWEEN_PHRASES_SEC = CHATGPT_WEB_PRE_SLEEP

__all__ = [
    "INACTIVE",
    "WEB_SLEEP_BETWEEN_PHRASES_SEC",
    "translate",
    "selenium_chrome_chatgpt_translate",
    "click_verify_human_checkbox_if_present",
]


def translate(ctx: RuntimeContext, text: str) -> tuple[bool, str]:
    """Block-mode translation entry point used by the active dispatcher.

    Honours :data:`WEB_SLEEP_BETWEEN_PHRASES_SEC` (0.0 by default —
    legacy parity), seeds the module globals the legacy body still
    reads, and delegates to :func:`selenium_chrome_chatgpt_translate`.
    Any exception (broken selector, captcha, network) collapses to
    ``(False, "")`` so the block-loop continues with an empty
    translation rather than hanging.
    """
    if WEB_SLEEP_BETWEEN_PHRASES_SEC > 0:
        time.sleep(WEB_SLEEP_BETWEEN_PHRASES_SEC)
    try:
        g = globals()
        g["driver"]         = ctx.browser.driver
        g["src_lang_name"]  = ctx.language.src_lang_name
        g["dest_lang_name"] = ctx.language.dest_lang_name
        # Seed the active RuntimeContext into module globals so the
        # legacy body can pass it back to ctx-aware helpers like
        # ``set_chrome_window_2_3_screen(ctx)`` without restructuring.
        g["ctx"]            = ctx
        g.setdefault("closed_cookies_accept_message_bool",  False)
        g.setdefault("close_install_extension_message_bool", False)
        g.setdefault("deepl_nb_clear_cached_times",          0)
        g.setdefault("engine_method",                        "web")
        g.setdefault("end_time",                             0.0)
        g.setdefault("elapsed_time",                         0.0)
        g.setdefault("json_configuration_array",             {})
        g.setdefault("logged_into_chatgpt",                  False)
        return selenium_chrome_chatgpt_translate(text, 2)
    except Exception as exc:
        print(f"[chatgpt_web] translate failed: {exc}")
        return False, ""


# Names referenced inside the function bodies that historically came from the
# entry script's module globals. Importing this module does NOT bind them; the
# functions are preserved verbatim for future re-wiring.
#   driver, src_lang_name, dest_lang_name,
#   closed_cookies_accept_message_bool,
#   close_install_extension_message_bool,
#   deepl_nb_clear_cached_times, json_configuration_array,
#   end_time, elapsed_time, engine_method, logged_into_chatgpt
# Helpers referenced from the active path:
#   safe_click, set_chrome_window_2_3_screen,
#   build_translation_prompt, get_nested_value_from_json_array.


def selenium_chrome_chatgpt_translate(to_translate, retry_count):
    global logged_into_chatgpt, src_lang_name, dest_lang_name
    
    translation = ""
    Translated = False
    # Progress bar to show only when deepl also shows it on the browser
    bar = None
    global closed_cookies_accept_message_bool, close_install_extension_message_bool, deepl_nb_clear_cached_times
    global engine_method, end_time, elapsed_time, json_configuration_array
    
    res = ""
    
    deepl_maximum_clear_cache_retry_key = ['deepl', 'maximum_clear_cache_retry']
    deepl_maximum_clear_cache_retry = get_nested_value_from_json_array(json_configuration_array, deepl_maximum_clear_cache_retry_key)
    
    # Set variable to false if they are not globally defined
    try:
        tmp_var = closed_cookies_accept_message_bool
        tmp_var = close_install_extension_message_bool
    except Exception:
        closed_cookies_accept_message_bool = False
        close_install_extension_message_bool = False

    to_translate_phrases_array = to_translate.split("\n")
    to_translate_phrases_array_len = len(to_translate_phrases_array)

    set_chrome_window_2_3_screen(ctx)  # ctx seeded by translate() wrapper

    try:
        translation_page_openeing_loop_count = 4
        translation_page_opened = False
        
        # Open ChatGPT translation page
        while translation_page_opened == False and translation_page_openeing_loop_count > 0:
            #print(f"{translation_page_openeing_loop_count} trying left")
            try:
                driver.delete_all_cookies()
                driver.get("https://chatgpt.com/")
                #sleep(1)

                translation_page_opened = True
            except Exception:
                print("Waiting for https://chatgpt.com/ ...")
                sleep(1)
            translation_page_openeing_loop_count = translation_page_openeing_loop_count - 1
        
        try:
            # Wait up to 1 second for the button to appear
            button = WebDriverWait(driver, 0.2).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept all')]"))
            )
            safe_click(driver, button)
            #print("✅ Clicked the 'Accept all' button.")
        except Exception:
            #print("⚠️ 'Accept all' button not found or not clickable (ignored).")
            pass
        
        try:
            # Wait until the link is visible
            stay_logged_out_link = stop_button = WebDriverWait(driver, CHATGPT_WEB_LOGGED_OUT_LINK_WAIT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Close']"))
            )
            
            # Click the link
            safe_click(driver, stay_logged_out_link)
        except Exception:
            pass

        try:
            # Wait until the link is visible
            stay_logged_out_link = stop_button = WebDriverWait(driver, CHATGPT_WEB_LOGGED_OUT_LINK_WAIT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Close']"))
            )

            # Click the link
            safe_click(driver, stay_logged_out_link)
        except Exception:
            pass

        try:
            WebDriverWait(driver, CHATGPT_WEB_STAY_LOGGED_OUT_WAIT).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Stay logged out')]"))
            ).click()
        except Exception:
            pass  # ignore if not found or not clickable

        # Locate the contenteditable div
        textarea = driver.find_element(By.XPATH, "//div[@id='prompt-textarea']")

        # Send text to the element
        safe_click(driver, textarea)

        #time.sleep(5)
        #textarea.send_keys("Translate this from English to Persian:")

        # Sending a new line using Keys.RETURN for proper formatting
        #textarea.send_keys(Keys.SHIFT + Keys.ENTER)

        #textarea.send_keys("I was lying with my eyes closed,")
        #textarea.send_keys(Keys.SHIFT + Keys.ENTER)


        # The string that needs to be sent
        # Max 4,096 characters ?
        
        str_prompt = build_translation_prompt(src_lang_name, dest_lang_name, to_translate)
        
        #print (str_prompt)
        
        lines = str_prompt.split('\n')

        # Split the string on new lines
        lines = str_prompt.splitlines()

        # Wrap each line in <p>...</p>
        wrapped_lines = [f"<p>{line}</p>" for line in lines]

        # Join all wrapped lines into a single string
        output_string = "".join(wrapped_lines)
        
        #print(f"to_translate_phrases_array_len={to_translate_phrases_array_len}")

        # JavaScript to set the content of the contenteditable div
        js_script = """
        var textarea = document.getElementById('prompt-textarea');
        textarea.innerHTML = arguments[0];
        """

        # Execute JavaScript to inject the text into the div
        driver.execute_script(js_script, output_string)

        # Send each line to the textarea
        #for i, line in enumerate(lines):
        #    textarea.send_keys(line)  # Send the current line
            
        #    # If it's not the last line, send SHIFT + ENTER to move to the next line
        #    if i < len(lines) - 1:
        #        textarea.send_keys(Keys.SHIFT + Keys.RETURN)

        # Let the composer register the injected text before we click submit.
        sleep(CHATGPT_WEB_AFTER_INJECT_SLEEP)
        #button = WebDriverWait(driver, 3).until(
        #    EC.presence_of_element_located((By.XPATH, "//button[@aria-label='Send prompt' and @data-testid='send-button']"))
        #)
        
        #button = WebDriverWait(driver, 3).until(
        #    EC.presence_of_element_located((By.CSS_SELECTOR, "#composer-submit-button > svg.icon > path"))
        #)

        try:
            button = driver.find_element(By.CSS_SELECTOR, 'button[data-testid="close-button"]')
            safe_click(driver, button)
        except Exception:
            pass

        # Locate the button element using its attributes
        button_submit_prompt = driver.find_element(By.ID, "composer-submit-button")
        
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button_submit_prompt)

        # Click the button
        safe_click(driver, button_submit_prompt)


        # Set a timeout value for waiting for the element
        timeout = 1  # Timeout after 10 seconds if not found
        found_stop_streaming_button = False
        
        max_wait_time = CHATGPT_WEB_MAX_STREAMING_WAIT  # seconds
        start_time = time.time()
        found_stop_streaming_button = False

        while time.time() - start_time < max_wait_time:
            try:
                # Search for the button with aria-label="Stop streaming"
                stop_button = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, "//button[@aria-label='Stop streaming']"))
                )
                
                # Element found, perform action (if any)
                if not found_stop_streaming_button:
                    #print("Found the 'Stop streaming' button. Waiting for the stop steaming button to disappear")
                    found_stop_streaming_button = True
                    
                
                # Stop-streaming still visible — keep polling
                time.sleep(CHATGPT_WEB_STREAMING_POLL)
                
                try:
                    close_button = WebDriverWait(driver, 0.01).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-testid='answer-mode-tabs-tab-search']"))
                    )

                    close_button = driver.find_element(By.CSS_SELECTOR, "button[data-testid='answer-mode-tabs-tab-search']")

                    # Send PAGE_DOWN to the body (or active element)
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
                    #print("Button clicked and PAGE_DOWN sent")
                except Exception:
                    try:
                        body = driver.find_element(By.TAG_NAME, "body")
                        body.send_keys(Keys.PAGE_DOWN)
                    except Exception:  #print("Cannot find html body...")
                        pass
                
                try:
                    # Wait until the link is visible
                    stay_logged_out_link = WebDriverWait(driver, 0.01).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Close']"))
                    )

                    # Click the link
                    safe_click(driver, stay_logged_out_link)
                except Exception:
                    pass

                try:
                    WebDriverWait(driver, 0.3).until(
                        EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Stay logged out')]"))
                    ).click()
                except Exception:
                    pass  # ignore if not found or not clickable
                    
                try:
                    # Wait briefly (0.5s) for the Close button to appear and be clickable
                    close_button = WebDriverWait(driver, 0.05).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='close-button']"))
                    )
                    safe_click(driver, close_button)
                    #print("✅ Clicked the 'Close' button.")
                except Exception:
                    #print("⚠️ 'Close' button not found or not clickable (ignored).")
                    pass
                    
                # Scroll down the page to see the translation
                try:
                    button = driver.find_element(
                        By.CSS_SELECTOR,
                        "button.cursor-pointer.absolute.z-30.rounded-full.bg-clip-padding.border.text-token-text-secondary"
                    )
                    safe_click(driver, button)
                except Exception:
                    pass  # Ignore if not found or not clickable
                
            except Exception as e:
                # If the element is no longer found or any other exception occurs
                #print("Element not found or timeout reached. Stopping the loop.")
                
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                break

        # Wait for the button to appear with a timeout of 3 seconds
        #button = WebDriverWait(driver, 3).until(
        #    EC.presence_of_element_located((By.XPATH, "//button[@aria-label='Dictate button']"))
        #)

        page_source_str = driver.page_source


        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(page_source_str, 'html.parser')

        # Find all the article tags
        articles = soup.find_all('article')

        # Legacy assumed at least 2 articles — index 0 is the user's
        # prompt, index 1 is ChatGPT's first response. If guest-session
        # rate-limits or Cloudflare gates the request, only the prompt
        # article (or zero) is in the DOM and the legacy ``articles[1]``
        # raises ``IndexError`` which the outer try/except catches —
        # but only after one full page-load wasted. Bail early instead.
        if len(articles) < 2:
            print(f"[chatgpt_web] no response article in DOM "
                  f"(found {len(articles)}). Likely rate-limit or "
                  f"Cloudflare gate on the guest session.")
            return False, ""

        second_article_html = str(articles[1])
        #print (second_article_html)
        #print()


        # Get the text of the last article element
        last_article_text = articles[-1].get_text()

        # Print the extracted text
        #print(last_article_text)

        lines = None

        # Find the div with class "markdown"
        markdown_div = articles[1].find('div', class_='markdown')

        # Check if the div exists and then process the text
        if markdown_div:
            # Step 1: Replace all </p><p> with <br/>
            html_str = str(markdown_div)
            html_str = html_str.replace('</p><p>', '<br/><br/>')

            # Reparse the modified HTML to a BeautifulSoup object again
            markdown_div = BeautifulSoup(html_str, 'html.parser')

            # Step 2: Define a complex delimiter for <br/>
            delimiter = 'random_complex_delimiter_123456'
            delimiter_paragraph = f"<p>{delimiter}</p>"

            # Step 3: Replace <br/> tags with the complex delimiter
            for line_break in markdown_div.find_all('br'):
                line_break.insert_before(BeautifulSoup(delimiter_paragraph, 'html.parser'))
                line_break.unwrap()  # Remove the <br> tag after inserting the delimiter
                

            # Get the full text with the complex delimiter and print it
            markdown_text_with_delimiter = markdown_div.get_text()

            # Output the result
            #print(markdown_text_with_delimiter)
            #input("After markdown text split")
            
            lines = markdown_text_with_delimiter.split(delimiter)
            if(len(lines) == 1):
                lines = markdown_text_with_delimiter.split("\n")
                
            lines = [line.replace('\n', '') for line in lines]
            #print("to_translate")
            #print(to_translate)
            #print(lines)
            #print("after print lines")

        else:
            print("Error : No div with class 'markdown' found.")

        translated_phrases_array = lines
        if translated_phrases_array is None:
            translated_phrases_array_len = 0
        else:
            translated_phrases_array_len = len(translated_phrases_array)
        #print(f"translated_phrases_array_len={translated_phrases_array_len}")
        
        input_nb_lines = len(to_translate.replace("\r", "").split("\n"))
        # for pos_remove in range(0,translated_phrases_array_len - to_translate_phrases_array_len):
        if translated_phrases_array_len >= to_translate_phrases_array_len:
            #print(f"input_nb_lines={input_nb_lines}")
            translated_phrases_array = translated_phrases_array[:input_nb_lines]
            #print("input_nb_lines: %s" % (input_nb_lines))
            #print("array: %s" % (translated_phrases_array))
            res = "\n".join(translated_phrases_array)
            if translated_phrases_array_len > to_translate_phrases_array_len:
                print("Too many lines found in translation...")
                res = ""
                translated_phrases_array = ""
                translated_phrases_array_len = 0
                print("Found %s lines out of %s lines" % (translated_phrases_array_len, to_translate_phrases_array_len))

        if translated_phrases_array_len < to_translate_phrases_array_len:
            res = ""
            print("Warning, not enough lines found in translation. Retrying.")
            print("Cleaning up chatgpt cookies...")
            driver.delete_all_cookies()

        translation = "\n".join(lines)
        #input("After markdown text")
        # Get the text inside this div
        #if assistant_div:
        #    assistant_text = assistant_div.get_text()
        #    print(assistant_text)
        #else:
        #    print("No div with data-message-author-role='assistant' found.")
        
        # Step 1: Click the 3-dot conversation options button
        try:
            menu_button = WebDriverWait(driver, 0.25).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="conversation-options-button"]'))
            )
            safe_click(driver, menu_button)

            # Step 2: Wait for and click the "Delete" button by visible text
            delete_button = WebDriverWait(driver, 0.25).until(
                EC.element_to_be_clickable((By.XPATH, "//*/text()[normalize-space(.)='Delete']/parent::*"))
            )
            safe_click(driver, delete_button)
            
            # Step: Click the red "Delete" confirmation button
            confirm_delete_button = WebDriverWait(driver, 0.25).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="delete-conversation-confirm-button"]'))
            )
            safe_click(driver, confirm_delete_button)
        except Exception:
            pass
        
            
    except Exception:
        var = traceback.format_exc()
        try:
            #This content may violate our usage policies.
            if "This content may violate our usage policies." in driver.page_source:
                print("Chatgpt returned an error : This content may violate our usage policies.")
            else:
                print(var)
        except Exception:
            pass
        #input("Wait")
    if res is not None and res != "":
        return True, translation
    else:
        return False, ""

def click_verify_human_checkbox_if_present(driver, timeout=50):
    """
    If a DIV containing the text "Verify you are human" has an input[type=checkbox] inside,
    scroll it into view and click it. Ignore errors and return True if clicked, False otherwise.
    """
    
    try:
        WebDriverWait(driver, 20).until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR,"iframe[title='Widget containing a Cloudflare security challenge']")))
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='checkbox']"))).click()
    except Exception:
        input("Did not find checkbox")
        
    return

    # Wait for iframe to load (Cloudflare Turnstile usually has "cf-chl-widget" or similar in its ID)
    iframe = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']"))
    )

    # Switch into the iframe
    driver.switch_to.frame(iframe)

    # Now find the checkbox inside the iframe
    checkbox = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox']"))
    )
    safe_click(driver, checkbox)

    # Switch back to main page
    driver.switch_to.default_content()
    return
    
    xpath = "//div[contains(., 'Verify you are human')]//input[@type='checkbox']"
    try:
        # wait briefly for presence (not necessarily visible/clickable)
        checkbox = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
    except TimeoutException:
        input("Didn't find checkbox")
        return False

    try:
        # Scroll into view
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", checkbox)
    except WebDriverException:
        # ignore scrolling errors
        pass

    try:
        # Use JS click for maximum reliability (avoids overlay / intercepted click issues)
        driver.execute_script("arguments[0].click();", checkbox)
        return True
    except (JavascriptException, WebDriverException):
        # fallback to normal click if JS click fails
        try:
            safe_click(driver, checkbox)
            return True
        except Exception:
            return False

