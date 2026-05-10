"""DeepL Selenium engine — login + close-messages + log-off + translate.

Extracted in Phase G3 from the entry script. Every function takes
``ctx: RuntimeContext`` as its first argument; reads/writes go through
``ctx.browser`` (driver, session flags), ``ctx.config``
(json_configuration_array, max_translation_block_size), and
``ctx.engine`` (method) where applicable.

R15 — DeepL phrasesblock → singlephrase fallback
------------------------------------------------
The fallback dance lives in main():

    if translation_succeded is False
       and ctx.engine.engine == 'deepl'
       and ctx.engine.method == 'phrasesblock':

        ctx.engine.method = 'singlephrase'             # flip method
        set_translation_function(ctx)                    # refresh dispatcher
        ctx.browser.driver.quit()                        # drop the driver
        create_webdriver(ctx)                            # rebuild it

This module owns ``selenium_chrome_deepl_translate`` (the per-call
translator) — the structural test
``test_deepl_phrasesblock_to_singlephrase_after_extraction`` verifies
the fallback flows through ctx after extraction.

Public API
----------
  - ``translate(ctx, text)``                — Engine Protocol entry point.
  - ``selenium_chrome_deepl_log_in(ctx)``   — login (legacy name).
  - ``selenium_chrome_deepl_log_off(ctx)``  — log off (legacy name).
  - ``deepl_close_messages(ctx)``           — close popups (legacy name).
  - ``selenium_chrome_deepl_translate(ctx, text, retry)`` — translator.
"""
from __future__ import annotations

import re
import time
import traceback
from time import sleep

import progressbar

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

from runtime import RuntimeContext
from selenium_utils import safe_click, set_chrome_window_2_3_screen

from config import (
    get_nested_value_from_json_array,
)


__all__ = [
    "translate",
    "selenium_chrome_deepl_log_in",
    "selenium_chrome_deepl_log_off",
    "deepl_close_messages",
    "selenium_chrome_deepl_translate",
]


# ── functions ────────────────────────────────────────────────────────────────


def selenium_chrome_deepl_log_in(ctx: RuntimeContext):
    """Log into DeepL with the credentials stored in the JSON configuration.

    Threaded in Phase F1.2: reads the JSON config and the maximum block
    size through ``ctx.config`` instead of the historical
    ``json_configuration_array`` / ``MAX_TRANSLATION_BLOCK_SIZE`` globals.
    """
    deepl_account_email_key = ['deepl', 'account', 'email']
    deepl_account_email = get_nested_value_from_json_array(ctx.config.json_configuration_array, deepl_account_email_key)

    deepl_account_password_key = ['deepl', 'account', 'password']
    deepl_account_password = get_nested_value_from_json_array(ctx.config.json_configuration_array, deepl_account_password_key)

    deepl_account_enabled_key = ['deepl', 'account', 'enabled']
    deepl_account_enabled = get_nested_value_from_json_array(ctx.config.json_configuration_array, deepl_account_enabled_key)
    
    #ctx.browser.driver.maximize_window()

    try:
        ctx.browser.driver.get("https://www.deepl.com/translator")
        
        try:
        
            try:
                # Accept cookies
                deepl_accept_cookies_element = "//button[contains(.,'Accept')]"
                deepl_accept_cookies_button = WebDriverWait(ctx.browser.driver, 1).until(
                    EC.presence_of_element_located((By.XPATH, deepl_accept_cookies_element)))
                ctx.browser.driver.execute_script("arguments[0].scrollIntoView();", deepl_accept_cookies_button)    
                safe_click(ctx.browser.driver, deepl_accept_cookies_button)
                
            except Exception:
                pass

            # Close the cookies message box if it is there
            try:
                if closed_cookies_accept_message_bool == False:
                    # Accept cookies
                    deepl_accept_cookies_element = "//button[contains(.,'Close')]"
                    deepl_accept_cookies_button = WebDriverWait(ctx.browser.driver, 1).until(
                        EC.presence_of_element_located((By.XPATH, deepl_accept_cookies_element)))
                    safe_click(ctx.browser.driver, deepl_accept_cookies_button)
                    closed_cookies_accept_message_bool = True
            except Exception:
                pass
                
            try:
                # close install extension message
                ctx.browser.driver.get("https://www.deepl.com/translator")
                deepl_close_deepl_extension_element = ".w-6 > .flex"
                deepl_close_deepl_extension_button = WebDriverWait(ctx.browser.driver, 0.05).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, deepl_close_deepl_extension_element)))
                safe_click(ctx.browser.driver, deepl_close_deepl_extension_button)
            except Exception:
                pass
        
            # End function if no email or password are provided
            if (deepl_account_email is None) or (deepl_account_email is None):
                return False
            elif deepl_account_enabled == False:
                return False
            
            ctx.browser.driver.set_window_position(0, 50)
            ctx.browser.driver.set_window_size(800, 700)
            ctx.browser.driver.get("https://www.deepl.com/en/login/")

            try:
                # Accept cookies
                deepl_accept_cookies_element = "//button[contains(.,'Accept all cookies')]"
                deepl_accept_cookies_button = WebDriverWait(ctx.browser.driver, 0.05).until(
                    EC.presence_of_element_located((By.XPATH, deepl_accept_cookies_element)))
                ctx.browser.driver.execute_script("arguments[0].scrollIntoView();", deepl_accept_cookies_button)    
                safe_click(ctx.browser.driver, deepl_accept_cookies_button)
                
            except Exception:
                pass       
            
            # Fill username 
            deepl_login_email_element = "//input[@name='email']"
            deepl_login_email_field = WebDriverWait(ctx.browser.driver, 2).until(
                EC.presence_of_element_located((By.XPATH, deepl_login_email_element)))
            deepl_login_email_field.send_keys(deepl_account_email)
            
            # Fill password
            deepl_login_password_element = "//input[@name='password']"
            deepl_login_password_field = WebDriverWait(ctx.browser.driver, 1).until(
                EC.presence_of_element_located((By.XPATH, deepl_login_password_element)))
            deepl_login_password_field.send_keys(deepl_account_password)
            sleep(1)

            # Close the cookies message box if it is there
            try:
                if closed_cookies_accept_message_bool == False:
                    # Accept cookies
                    deepl_accept_cookies_element = "//button[contains(.,'Close')]"
                    deepl_accept_cookies_button = WebDriverWait(ctx.browser.driver, 0.5).until(
                        EC.presence_of_element_located((By.XPATH, deepl_accept_cookies_element)))
                    safe_click(ctx.browser.driver, deepl_accept_cookies_button)
                    closed_cookies_accept_message_bool = True
            except Exception:
                pass
                
            try:
                # Accept cookies
                deepl_accept_cookies_element = "//button[contains(.,'Accept all cookies')]"
                deepl_accept_cookies_button = WebDriverWait(ctx.browser.driver, 0.05).until(
                    EC.presence_of_element_located((By.XPATH, deepl_accept_cookies_element)))
                ctx.browser.driver.execute_script("arguments[0].scrollIntoView();", deepl_accept_cookies_button)    
                safe_click(ctx.browser.driver, deepl_accept_cookies_button)
                
            except Exception:
                pass       
            
            # Submit login
            deepl_login_submit_element = "//form/button"
            deepl_login_submit_element = "//input[@name='submit']"
            deepl_login_submit_element = "//button[contains(.,'Log in')]"
            deepl_login_submit_button = WebDriverWait(ctx.browser.driver, 3).until(
                EC.presence_of_element_located((By.XPATH, deepl_login_submit_element)))
            ctx.browser.driver.execute_script("arguments[0].scrollIntoView();", deepl_login_submit_button)    
            sleep(1.5)
            try:
                safe_click(ctx.browser.driver, deepl_login_submit_button)
            except Exception:
                pass
            
            try:
                # Check account button exist
                deepl_login_menu_element = ".dl_header_menu_v2__buttons__opener"
                deepl_login_menu_button = WebDriverWait(ctx.browser.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, deepl_login_menu_element)))
                safe_click(ctx.browser.driver, deepl_login_menu_button)
                # Close the opener dialog, not required but cleaner
                sleep(0.1)
                safe_click(ctx.browser.driver, deepl_login_menu_button)
            except Exception:
                pass
            
            try:
                # Close the annoying plugin for deepl if displayed - bug : it does not find this element
                deepl_plugin_dialog_element = ".w-6 path"
                deepl_plugin_dialog_button = WebDriverWait(ctx.browser.driver, 0.05).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, deepl_plugin_dialog_element)))
                safe_click(ctx.browser.driver, deepl_plugin_dialog_button)
            except Exception:  # Just ignore if this plugin dialog does not appear
                pass
            
            # Success change block size if value exists
            deepl_max_char_bloc_size_key = ['deepl', 'account','maximum_character_block']
            deepl_maximum_character_block = get_nested_value_from_json_array(ctx.config.json_configuration_array, deepl_max_char_bloc_size_key)

            if isinstance(deepl_maximum_character_block, int):
                if deepl_maximum_character_block > ctx.config.max_translation_block_size:
                    ctx.config.max_translation_block_size = deepl_maximum_character_block
                    print("\nRobot is now logged in Deepl using %s account." % (deepl_account_email))
                    print("Changing the value of maximum number of characters per block: %s\n" % (ctx.config.max_translation_block_size))
                
            return True
            
        except Exception:
            var = traceback.format_exc()
            print(var)
            print("Failed to login into Deepl, continuing without being logged on.")
            ctx.browser.driver.set_window_size(800, 700)
            return False

    except Exception:
        var = traceback.format_exc()
        print(var)
        print("Failed to login into Deepl, continuing without being logged on.")
        ctx.browser.driver.set_window_size(800, 700)
        return False



def selenium_chrome_deepl_log_off(ctx: RuntimeContext):
    """Log out of DeepL.

    Threaded in Phase F1.2: takes ctx so main() can invoke it through a
    threaded chain in Phase F1.6. The vestigial
    ``global json_configuration_array, MAX_TRANSLATION_BLOCK_SIZE``
    declarations were dropped — neither was actually used here.
    """
    try:
        ctx.browser.driver.get("https://www.deepl.com/")
        
        try:
            
            # Open account menu by clicking the account button
            deepl_login_menu_element = ".dl_header_menu_v2__buttons__opener"
            deepl_login_menu_button = WebDriverWait(ctx.browser.driver, 9).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, deepl_login_menu_element)))
            safe_click(ctx.browser.driver, deepl_login_menu_button)
            
            try:
                # Open account menu by clicking the account button
                deepl_logout_menu_element = "//button[contains(.,'Log out')]"
                deepl_logout_menu_button = WebDriverWait(ctx.browser.driver, 1).until(
                    EC.presence_of_element_located((By.XPATH, deepl_logout_menu_element)))
                safe_click(ctx.browser.driver, deepl_logout_menu_button)
                print("\nRobot is now logged off Deepl account.")
                
            except Exception:  # Just ignore if this plugin dialog does not appear
                print("Unable to log off from Deepl, this can be ignored.")
                pass
                
            return True
            
        except Exception:
            var = traceback.format_exc()
            print(var)
            print("Failed of Deepl, this can be ignored")
            return False

    except Exception:
        var = traceback.format_exc()
        print(var)
        print("Failed of Deepl, this can be ignored")
        return False


def deepl_close_messages(ctx: RuntimeContext):
    """Close all common DeepL popups, messages, and dialogs.

    Threaded in Phase F1.5: reads/writes
    ``ctx.browser.closed_cookies_accept_message_bool``,
    ``ctx.browser.close_install_extension_message_bool``, and
    ``ctx.browser.driver`` instead of the historical module globals.
    """
    drv = ctx.browser.driver
    ctx.browser.close_install_extension_message_bool = False

    xpath_selectors = [
        "//button[contains(.,'Accept all cookies')]",
        "//button[contains(.,'Close')]",
        "//button[contains(.,'Accept')]",
        "//button[contains(.,'Got it')]",
        "//button[contains(.,'Dismiss')]",
        "//div[@role='dialog']//button[@aria-label='Close']",
        "//button[@aria-label='Close AI Labs banner button']",
        "//div[@data-testid='above-navigation-banner']//button[.//svg]",
        "//div[@data-testid='above-navigation-banner']//button",
    ]
    css_selectors = [
        ".w-6 > .flex",   # install-extension popup
    ]

    for selector in xpath_selectors:
        try:
            el = WebDriverWait(drv, 0.01).until(
                EC.presence_of_element_located((By.XPATH, selector))
            )
            drv.execute_script(
                "arguments[0].scrollIntoView({block: 'start', behavior: 'auto'});", el
            )
            safe_click(drv, el)
            if "cookies" in selector.lower():
                ctx.browser.closed_cookies_accept_message_bool = True
            if "w-6" in selector:
                ctx.browser.close_install_extension_message_bool = True
        except Exception:
            continue

    for selector in css_selectors:
        try:
            el = WebDriverWait(drv, 0.01).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            drv.execute_script(
                "arguments[0].scrollIntoView({block: 'start', behavior: 'auto'});", el
            )
            safe_click(drv, el)
            ctx.browser.close_install_extension_message_bool = True
        except Exception:
            continue

    if ctx.browser.close_install_extension_message_bool:
        # One more pass — some popups stack and only surface after the first close.
        deepl_close_messages(ctx)




def selenium_chrome_deepl_translate(ctx: RuntimeContext, to_translate, retry_count):
    translation = ""
    Translated = False
    # Progress bar to show only when deepl also shows it on the browser
    bar = None
    
    deepl_maximum_clear_cache_retry_key = ['deepl', 'maximum_clear_cache_retry']
    deepl_maximum_clear_cache_retry = get_nested_value_from_json_array(ctx.config.json_configuration_array, deepl_maximum_clear_cache_retry_key)
    
    # Set variable to false if they are not globally defined
    try:
        tmp_var = ctx.browser.closed_cookies_accept_message_bool
        tmp_var = ctx.browser.close_install_extension_message_bool
    except Exception:
        ctx.browser.closed_cookies_accept_message_bool = False
        ctx.browser.close_install_extension_message_bool = False

    to_translate_phrases_array = to_translate.split("\n")
    to_translate_phrases_array_len = len(to_translate_phrases_array)

    set_chrome_window_2_3_screen(ctx)


    def ensure_target_language(driver, dest_lang="fr", dest_lang_name="French", timeout=20):
        try:
            wait = WebDriverWait(ctx.browser.driver, timeout)

            # Retry loop to handle stale references
            for _ in range(3):
                try:
                    deepl_close_messages(ctx)
                    
                    # Re-query the element every iteration
                    lang_elem = wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, '[data-testid="translator-target-lang"]')
                        )
                    )
                    current_code = lang_elem.get_attribute("dl-selected-lang")
                    if current_code is not None:
                        current_code = current_code.lower()

                    if current_code == dest_lang:
                        return  # Already correct

                    # Open selector
                    wait.until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, '[data-testid="translator-target-lang-btn"]')
                        )
                    ).click()

                    # Select language by visible name
                    option = wait.until(
                        EC.element_to_be_clickable(
                            (By.XPATH, f"//button[.//text()[contains(., '{dest_lang_name}')]]")
                        )
                    )
                    option.click()

                    # Verify switch completed
                    wait.until(
                        lambda d: d.find_element(
                            By.CSS_SELECTOR,
                            '[data-testid="translator-target-lang"]'
                        ).get_attribute("dl-selected-lang") == dest_lang
                    )

                    return  # Success
                except StaleElementReferenceException:
                    # Element got replaced; retry
                    continue

            print(f"[WARNING] Failed to ensure target language '{dest_lang_name}' ({dest_lang}): stale element after retries")

        except Exception as e:
            print(f"[WARNING] Failed to ensure target language '{dest_lang_name}' ({dest_lang}): {e}")
            
    def ensure_target_language_new_error(driver,
                           dest_lang="zh-hans",
                           dest_lang_name="Chinese (Simplified)",
                           timeout=15):

        wait = WebDriverWait(ctx.browser.driver, timeout)

        dest_lang = dest_lang.lower()
        dest_lang_name = dest_lang_name.lower()

        try:
            # 1️⃣ Check if already selected (avoid opening dropdown)
            current = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[data-testid="translator-target-lang"]')
                )
            ).get_attribute("dl-selected-lang")

            if current and current.lower() == dest_lang:
                return

            # 2️⃣ Open dropdown
            wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, '[data-testid="translator-target-lang-btn"]')
                )
            ).click()

            # 3️⃣ Try direct click by data-testid (MOST STABLE)
            normalized_code = dest_lang.replace("-hans", "-Hans").replace("-hant", "-Hant").replace("-br", "-BR")

            try:
                locator = (By.CSS_SELECTOR,
                           f'[data-testid="translator-lang-option-{normalized_code}"]')

                wait.until(EC.element_to_be_clickable(locator)).click()

            except TimeoutException:
                # 4️⃣ Fallback: match by visible text (case insensitive)
                xpath = (
                    "//button[@role='option' and "
                    "contains(translate(normalize-space(string(.)), "
                    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                    "'abcdefghijklmnopqrstuvwxyz'), "
                    f"'{dest_lang_name}')]"
                )

                wait.until(EC.element_to_be_clickable((By.XPATH, xpath))).click()

            # 5️⃣ Wait until switch confirmed
            wait.until(
                lambda d: d.find_element(
                    By.CSS_SELECTOR,
                    '[data-testid="translator-target-lang"]'
                ).get_attribute("dl-selected-lang").lower() == dest_lang
            )

        except Exception as e:
            #var = traceback.format_exc()
            #print(var)
            return False
            #print(f"[WARNING] Failed to ensure target language '{dest_lang_name}' ({dest_lang}): {e}")
            
    try:
        translation_page_openeing_loop_count = 4
        translation_page_opened = False
        
        # Open Deepl translation page
        while translation_page_opened == False and translation_page_openeing_loop_count > 0:
            #print(f"{translation_page_openeing_loop_count} trying left")
            try:
                # ctx.browser.driver.get("https://www.deepl.com/translator#%s/%s/%s" % (src_lang,dest_lang, to_translate))
                # Deepl has a bug for / in text to be translated
                # must be replaced by %5C%2F
                #translation_url = "https://www.deepl.com/translator#%s/%s/%s" % (
                #src_lang, dest_lang, urllib.parse.quote(to_translate).replace("%5C", "%5C%5C").replace("/", "%5C%2F").replace("%7C", "%5C%7C"))
                translation_url = "https://www.deepl.com/translator#%s/%s/" % (src_lang, dest_lang)
                ctx.browser.driver.get(translation_url)
                try:
                    (ctx.browser.driver.page_source).encode('utf-8')
                    WebDriverWait(ctx.browser.driver, 15).until(lambda d: d.execute_script('return document.readyState') == 'complete')
                except Exception:
                    pass
                
                # Make sure the target language matches with the target language code or at least the target language name
                try:
                    ensure_target_language(ctx.browser.driver, dest_lang=dest_lang, dest_lang_name=dest_lang_name)
                    WebDriverWait(ctx.browser.driver, 15).until(lambda d: d.execute_script('return document.readyState') == 'complete')
                except Exception:
                    pass
                    
                translation_page_opened = True
                
                deepl_close_messages(ctx)
                
                ############################################
                # Copy the text inside using javascript
                ############################################
                try:
                    js_script = """
                    // Select DeepL's editable input area
                    var textarea = document.querySelector('d-textarea[data-testid="translator-source-input"] div[contenteditable="true"]');
                    if (textarea) {
                        // Set plain text content (not HTML)
                        textarea.textContent = arguments[0];

                        // Simulate real user input so DeepL's JS reacts
                        textarea.dispatchEvent(new InputEvent('input', { bubbles: true }));
                        textarea.dispatchEvent(new Event('change', { bubbles: true }));
                        textarea.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: ' ' }));
                    }
                    """
                    ctx.browser.driver.execute_script(js_script, to_translate)
                except Exception:
                    pass  
                
            except Exception:
                print("Waiting for https://www.deepl.com/ ...")
                sleep(1)
            translation_page_openeing_loop_count = translation_page_openeing_loop_count - 1
            # ctx.browser.driver.get("https://www.deepl.com/translator#%s/%s/Hello" % (src_lang,dest_lang))

        # Wait for page to be loaded
        try:
            (ctx.browser.driver.page_source).encode('utf-8')
            WebDriverWait(ctx.browser.driver, 15).until(lambda d: d.execute_script('return document.readyState') == 'complete')

            try:
                # Accept cookies
                deepl_accept_cookies_element = "//button[contains(.,'Accept')]"
                deepl_accept_cookies_button = WebDriverWait(ctx.browser.driver, 0.01).until(
                    EC.presence_of_element_located((By.XPATH, deepl_accept_cookies_element)))
                ctx.browser.driver.execute_script("arguments[0].scrollIntoView();", deepl_accept_cookies_button)    
                safe_click(ctx.browser.driver, deepl_accept_cookies_button)
                
            except Exception:
                pass
            #print("Page loaded completed")
        except Exception:  # print("Waiting for the input_element...")
            var = traceback.format_exc()
            print(var)
        
        deepl_close_messages(ctx)
        
        # Wait for copy translation button
        # Removed on 2022-05-25
        found_copy_button = False
        loop_counter_search_button = 4
        while (found_copy_button is False) and (loop_counter_search_button > 0):
            #print(f"loop {loop_counter_search_button}")
            deepl_close_messages(ctx)
            
            try:
                # Accept cookies
                deepl_translation_section_element = "section[aria-labelledby='translation-target-heading']"
                
                deepl_translation_section = WebDriverWait(ctx.browser.driver, 0.01).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, deepl_translation_section_element)
                    )
                )
                is_visible = ctx.browser.driver.execute_script("""
                    const r = arguments[0].getBoundingClientRect();
                    return (r.top >= 0 && r.bottom <= window.innerHeight);
                """, copy_translation_button)
                if not is_visible:
                    ctx.browser.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'end'});",
                        copy_translation_button
                    )
            except Exception:
                pass
            
            try:
                # Added on 2023-09-26
                copy_translation_element = "//button[contains(@aria-label, 'Copy to clipboard')]" #//svg
                #print(f"Looking for {copy_translation_element}")
                copy_translation_button = WebDriverWait(ctx.browser.driver, 0.2).until(
                    EC.presence_of_element_located((By.XPATH, copy_translation_element)))
                
                found_copy_button = True
                #print(f"Loop {loop_counter_search_button}, found xpath button: {copy_translation_element}")
                #print(f"Found xpath button: {copy_translation_element}")
                time.sleep(0.2)
                
            except Exception:  #print(f"Except loop {loop_counter_search_button}, not found xpath button: {copy_translation_element}")
                try:
                    copy_translation_element = "#dl_translator"
                    #print(f"Looking for {copy_translation_element}")

                    copy_translation_button = WebDriverWait(ctx.browser.driver, 0.2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, copy_translation_element)))
                                                                                                                                      
                    found_copy_button = True
                    #print(f"Found xpath button: {copy_translation_element}")
                    
                except Exception:
                    try:
                        # Version 2022-03-09
                        copy_translation_element = ".lmt__target_toolbar_right > span path:nth-child(2)"
                        copy_translation_element = "div:nth-child(5) > svg"
                        #print(f"Looking for {copy_translation_element}")
                        copy_translation_button = WebDriverWait(ctx.browser.driver, 0.2).until(
                            EC.presence_of_element_located((By.XPATH, copy_translation_element)))
                        found_copy_button = True
                    except Exception:  # Version 2022-03-30
                        try:
                           copy_translation_element = ".lmt__target_toolbar_right > div > span svg"
                           #print(f"Looking for {copy_translation_element}")       
                           copy_translation_button = WebDriverWait(ctx.browser.driver, 0.2).until(
                               EC.presence_of_element_located((By.CSS_SELECTOR, copy_translation_element)))
                           found_copy_button = True
                        except Exception:  #print("Copy button not found !!")
                           pass
            #print("Incrementing loop_counter_search_button")
            loop_counter_search_button = loop_counter_search_button - 1
        
        busy_element = ".lmt__textarea_separator__border_inner"
        # busy_element = "//div[@id='dl_translator']/div/div/div[5]"
        sleep(ctx.browser.deepl_sleep_wait_translation_seconds)

        busybox_innerhtml = ""
        timeout_busy_translating = 50
        
        try:
            busybox = WebDriverWait(ctx.browser.driver, 0.3).until(EC.presence_of_element_located((By.CSS_SELECTOR, busy_element)))
            attrs = ctx.browser.driver.execute_script(
                'var items = {}; for (index = 0; index < arguments[0].attributes.length; ++index) { items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value }; return items;',
                busybox)
            busybox_innerhtml = busybox.get_attribute('innerHTML')
            while busybox_innerhtml != "" and timeout_busy_translating > 0:
                sleep(0.3)
                busybox = WebDriverWait(ctx.browser.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, busy_element)))
                busybox_innerhtml = busybox.get_attribute('innerHTML')
                attrs = ctx.browser.driver.execute_script(
                    'var items = {}; for (index = 0; index < arguments[0].attributes.length; ++index) { items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value }; return items;',
                    busybox)
                timeout_busy_translating -= 1

                deepl_usage_limit_reached_element = "//button[contains(.,'Back to Translator')]"
                try:
                    deepl_usage_limit_reached_button = WebDriverWait(ctx.browser.driver, 0.05).until(
                        EC.presence_of_element_located((By.XPATH, deepl_usage_limit_reached_element)))
                    safe_click(ctx.browser.driver, deepl_usage_limit_reached_button)
                    return False, ""
                except Exception:
                    pass
        except Exception:  #var = traceback.format_exc()
            #print(var)
            limit_reached = False

            # Look for usage limit reached, and try pro for 30 days
            deepl_usage_limit_reached_element = "//button[contains(.,'Back to Translator')]"
            try:
                deepl_usage_limit_reached_button = WebDriverWait(ctx.browser.driver, 0.05).until(
                    EC.presence_of_element_located((By.XPATH, deepl_usage_limit_reached_element)))
                
                limit_reached = True
                #safe_click(ctx.browser.driver, deepl_usage_limit_reached_button)
            except Exception:
                pass
            # Sometimes the busy element does not show up, just ignore it and continue
            
            deepl_close_messages(ctx)
            
            if limit_reached:
                try:
                    if ctx.browser.deepl_nb_clear_cached_times is None:
                        ctx.browser.deepl_nb_clear_cached_times = 0
                except Exception:
                    ctx.browser.deepl_nb_clear_cached_times = 0
                    
                if ctx.browser.deepl_nb_clear_cached_times > deepl_maximum_clear_cache_retry:
                    return False, ""
                print("Warning : deepl usage limit reached... retrying after cleaning cache.")
                ctx.browser.driver.delete_all_cookies()
                ctx.browser.driver.get("https://www.deepl.com")
                ctx.browser.closed_cookies_accept_message_bool = False
                ctx.browser.deepl_nb_clear_cached_times = ctx.browser.deepl_nb_clear_cached_times + 1
                ctx.browser.logged_into_deepl = selenium_chrome_deepl_log_in(ctx)
                return selenium_chrome_deepl_translate(ctx, to_translate, retry_count)
              

        #print("Scroll to copy_translation_button")
        actions = ActionChains(ctx.browser.driver)
        # actions.move_to_element(copy_translation_button).perform()
        # sleep(0.1)

        # Scroll the browser to the element's Y position
        try:
            ctx.browser.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'end'});",
                copy_translation_button
            )
        except Exception:
            pass

        copy_button_clicked = False
        copy_button_clicked_loop_count = 7
        res = ""
        still_translating_html_str = 'div class="lmt__progress_popup lmt__progress_popup--visible lmt__progress_popup--visible_2" dl-test="translator-progress-popup"'
        
        # When failing to get translation from HTML, use button copy and clipboard and warn user.
        warned_using_clipboard = False
        
        while copy_button_clicked_loop_count > 0 and (res == "" or res is None):
            #print(f"copy_button_clicked_loop_count : {copy_button_clicked_loop_count}")
            try:
                #ctx.browser.driver.execute_script("scrollBy(0,-1000);")
                # clipboard.copy('')
                #try:
                #    actions.move_to_element(copy_translation_button).perform()
                #except:
                #    pass
                sleep(0.05)
                # ctx.browser.driver.set_window_size(800, 700)
                page_source_str = ctx.browser.driver.page_source
                #print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::")
                #with open('before.html', 'w', encoding="utf-8") as f:
                #    f.write(page_source_str)
                #    f.close()
                wait_translation_finish_try = 400
                block_translation_percent_done = 0
                while page_source_str.find(still_translating_html_str) > 0 and wait_translation_finish_try > 0:
                    sleep(0.05)
                    print("Still translating...")
                    page_source_str = ctx.browser.driver.page_source
                    # print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::")
                    # print(ctx.browser.driver.page_source)
                    wait_translation_finish_try = wait_translation_finish_try - 1
                    search_percent_re = r'of characters translated">(\d+)\% of characters translated</p>'
                    mo = re.search(search_percent_re, page_source_str)
                    if mo:
                        try:
                            if bar is None:
                                bar = progressbar.ProgressBar().start()
                                bar.maxval = 100

                            block_previous_translation_percent_done = block_translation_percent_done
                            block_translation_percent_done = mo.group(1)
                            if block_previous_translation_percent_done != block_translation_percent_done:
                                # print ("found percent: %s" %block_translation_percent_done)
                                bar.update(int(block_translation_percent_done))
                        except Exception:
                            pass

                    # input("of characters translated")
                
                if bar is not None:
                    bar.update(100)
                    bar = None
                    print("")

                # print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::")
                # print(ctx.browser.driver.page_source)
                # print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::")
                # input("enter to click on button")

                page_source_str = ctx.browser.driver.page_source
                # with open('after.html', 'w', encoding="utf-8") as f2:
                #    f2.write(page_source_str)
                # f2.close()
                # input("wait html")

                # print("Done waiting for translation")

                try:
                    # Try to get the translation from the innerhtml of translation button
                    inner_html_plain_text_element = "//button[@class='lmt__translations_as_text__text_btn']"
                    InnerHTMLPlainTextElement = WebDriverWait(ctx.browser.driver, 1).until(
                        EC.presence_of_element_located((By.XPATH, inner_html_plain_text_element)))
                    translation_from_plain_text = InnerHTMLPlainTextElement.get_attribute('innerHTML')
                    res = translation_from_plain_text
                except Exception:  # if we cannot find translation button with translation the use the copy button
                    # previous_clipbboard = clipboard.paste()
                    # previous_clipbboard = pyperclip.paste()
                    page_source_str = ctx.browser.driver.page_source
                    #with open('deepl_page_source.html', 'w', encoding="utf-8") as f:
                    #    f.write(page_source_str)
                    #    f.close()
                    res = ""
                    try:
                        try:
                            translation_box = WebDriverWait(ctx.browser.driver, 5).until(
                                EC.presence_of_element_located(
                                    (By.CSS_SELECTOR,
                                     "d-textarea[data-testid='translator-target-input'] div[contenteditable='true']")
                                )
                            )

                            res = translation_box.get_attribute("innerText")
                        except Exception:
                            var = traceback.format_exc()
                            print(var)
                            res = ""
                        
                        #try:
                        #    #inner_html_translation_xpath_element = '//div[@contenteditable="true" and @role="textbox" and @aria-labelledby="translation-results-heading"]'
                        #    inner_html_translation_xpath_element = "//div[contains(@aria-labelledby, 'translation-target-heading')]"
                        #    InnerHTMLTranslationElement = WebDriverWait(ctx.browser.driver, 1).until(
                        #        EC.presence_of_element_located((By.XPATH, inner_html_translation_xpath_element)))
                        #    
                        #    if InnerHTMLTranslationElement:
                        #        # Get the plain text from the element
                        #        translation_from_plain_text = InnerHTMLTranslationElement.text
                        #        #print("Plain Text: %s " % (translation_from_plain_text))
                        #    else:
                        #        print("Element not found")
                        #    res = translation_from_plain_text
                        #except:
                        #    var = traceback.format_exc()
                        #    print(var)
                    
                        # Added on version 2022-05-31
                        #copy_translation_element = '//*[@id="headlessui-tabs-panel-7"]/div/div[1]/section/div/div[2]/div[3]/section/div[2]/div[3]/span[2]/span/span/button'
                        #copy_translation_button = WebDriverWait(ctx.browser.driver, 6).until(
                        #    EC.presence_of_element_located((By.XPATH, copy_translation_element)))
                        if not warned_using_clipboard and (res == "" or res == None):
                            print("Warning: Failed to get translation from html, copying from clipboard")
                            warned_using_clipboard = True
                            
                        if warned_using_clipboard and (res == "" or res == None):
                            #return False, None
                            clipboard.copy('')
                            safe_click(ctx.browser.driver, copy_translation_button)
                            copy_button_clicked = True
                            res = clipboard.paste()
                            if len(res) == 0 or res == None:
                                print("Error : failed to get translation from Deepl.")
                                return False, ""
                            
                    except Exception:
                        var = traceback.format_exc()
                        print(var)
                        #print("res : %s" %(res))
                        pass
                    #return False, None
                    # res = pyperclip.paste()
                    # print(res)

                # id="target-dummydiv"
                # contains the translation
                res = res.replace("\r", "")
                res = re.sub(r"\n+", "\n", res)
                res = remove_span_tag(res)
                
                input_nb_lines = len(re.sub(r"\n+", "\n", to_translate).replace("\r", "").split("\n"))

                translated_phrases_array = res.split("\n")
                if translated_phrases_array is None:
                    translated_phrases_array_len = 0
                else:
                    translated_phrases_array_len = len(translated_phrases_array)
                
                translated_phrases_array = translated_phrases_array[:input_nb_lines]
                
                to_translate_phrases_array_len = input_nb_lines
                
                #print(input_nb_lines)
                #print(re.sub(r"\n+", "\n", to_translate).replace("\r", "").split("\n"))
                #print(translated_phrases_array_len)
                #print(translated_phrases_array)
                #print(translated_phrases_array_len)
                #print(to_translate_phrases_array_len)
                #input("Wait")
                
                # for pos_remove in range(0,translated_phrases_array_len - to_translate_phrases_array_len):
                if translated_phrases_array_len == to_translate_phrases_array_len:
                    res = "\n".join(translated_phrases_array)
                    
                if translated_phrases_array_len < to_translate_phrases_array_len or translated_phrases_array_len > to_translate_phrases_array_len:
                    res = ""

            except Exception:  #print(f"Found exception on loop {copy_button_clicked_loop_count}")
                if copy_button_clicked_loop_count < 20:
                    print("Waiting for the copy button...")
                    #var = traceback.format_exc()
                    #print(var)
            copy_button_clicked_loop_count = copy_button_clicked_loop_count - 1
        
        # translation = res
        translation = "\n".join(translated_phrases_array)
        # print("translation=%s" % (translation))
        # input("Press enter to continue")
    except Exception:
        var = traceback.format_exc()
        print(var)
        sleep(1)
        # sys.exit(0)
    if res == "":
        return False, ""
    else:
        return True, translation






# ── Engine Protocol entry point ──────────────────────────────────────────────

def translate(ctx: RuntimeContext, text: str) -> tuple[bool, str]:
    """Engine Protocol implementation.

    Returns ``(success, translated)`` per ``engines._base.Engine``. The
    underlying ``selenium_chrome_deepl_translate`` already returns this
    shape; we just wrap it to match the Protocol.
    """
    return selenium_chrome_deepl_translate(ctx, text, 0)
