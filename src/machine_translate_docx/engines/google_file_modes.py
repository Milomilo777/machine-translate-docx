"""Google file-mode workers — extracted from cli.py in Sprint D-B (2026-05-16).

These ten functions implement Google's "file-mode" translation paths:
upload the whole document to translate.google.com instead of feeding
phrases through the textarea one at a time. The default
``singlephrase`` method covers most use cases; this cluster handles
``--enginemethod textfile`` / ``htmljavascript`` / ``xlsxfile``.

Cluster layout
--------------

| Function                                                       | Role                                  |
|---                                                             |---                                    |
| :func:`google_translate_from_text_file`                        | top-level dispatcher (textfile mode)  |
| :func:`google_translate_from_html_javascript`                  | top-level dispatcher (htmljavascript) |
| :func:`google_translate_from_html_xlsxfile`                    | top-level dispatcher (xlsxfile mode)  |
| :func:`selenium_chrome_google_translate_text_file`             | textfile worker                       |
| :func:`selenium_chrome_google_translate_html_javascript_file`  | html/javascript worker                |
| :func:`selenium_chrome_google_translate_xlsx_file`             | xlsx worker                           |
| :func:`generate_text_file_from_phrases`                        | helper — build text from phrases      |
| :func:`generate_html_file_from_phrases_for_google_translate_javascript` | helper — build html          |
| :func:`generate_xlsx_file_from_phrases`                        | helper — build xlsx                   |
| :func:`get_last_downloaded_file_path`                          | helper — poll chrome downloads        |

The three top-level dispatchers are also re-exported from
:mod:`engines/__init__` so :func:`cli.translate_docx` can import
them via ``from .engines import google_translate_from_*`` cleanly.

Lazy import pattern
-------------------
Most of these functions read several ``cli`` module globals by bare
name (``xtm``, ``xlsxreplacefile``, ``from_text_table``, ``src_lang``,
``docx_file_name`` etc.). The legacy code mirrored those onto the
module namespace via the Phase H ``_sync_globals_from_ctx`` bridge.
Here we keep behaviour identical by lazy-importing the names from
``machine_translate_docx.cli`` inside each function body — mirroring
the :mod:`docx_io.parse:88` pattern. ``end_time`` / ``elapsed_time``
caveats from :mod:`statistics` do not apply to this cluster.

Behaviour preservation
----------------------
The legacy bodies contain long-standing latent bugs that the
extraction preserves verbatim — fixing them is out of scope for
this sprint:

* :func:`selenium_chrome_google_translate_xlsx_file`'s
  ``except Exception`` recovery branch sets ``self.wb = None`` —
  ``self`` is undefined in a module-level function, so the line
  raises ``NameError`` if Workbook construction fails. The next
  line is ``sys.exit(13)`` though, so the ``NameError`` masks an
  intentional exit.
* :func:`get_last_downloaded_file_path` reads ``driver`` as a bare
  name in both its inner and outer scopes. Resolved here by
  lazy-importing ``cli.driver`` into a local at the function entry,
  which the inner ``chrome_downloads(drv)`` closure picks up.
* :func:`google_translate_from_html_javascript` reads
  ``html_file_path`` as a bare name immediately after calling
  :func:`generate_html_file_from_phrases_for_google_translate_javascript`,
  which only writes the path to a *local* variable. The lookup
  resolves through cli's module-level ``html_file_path = ''``
  default, so the dispatcher always passes the empty string to the
  worker. Pre-existing bug — preserved.

Drive-by improvement
--------------------
``sys.exit(7)`` in
:func:`selenium_chrome_google_translate_text_file`'s ``except`` is
replaced with ``raise TranslationFailure(reason=
"google_file_mode_error", …)``. This routes the failure through
``main()``'s structured-failure path so the launcher's stdout
parser flips the job to ``status=error`` (P2 from the
2026-05-16 master audit). The sibling ``sys.exit(8)`` and
``sys.exit(13)`` are left as-is for this commit — the launcher's
non-zero-exit detection still covers them.
"""
from __future__ import annotations

import html
import os
import platform
import re
import sys
import time
import traceback
from typing import TYPE_CHECKING

import progressbar
from bs4 import BeautifulSoup
from openpyxl import Workbook
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ..exceptions import TranslationFailure
from ..selenium_utils import safe_click
from .google import selenium_chrome_google_click_cookies_consent_button

if TYPE_CHECKING:
    from ..runtime import RuntimeContext


__all__ = [
    "selenium_chrome_google_translate_text_file",
    "selenium_chrome_google_translate_html_javascript_file",
    "selenium_chrome_google_translate_xlsx_file",
    "get_last_downloaded_file_path",
    "generate_html_file_from_phrases_for_google_translate_javascript",
    "generate_text_file_from_phrases",
    "generate_xlsx_file_from_phrases",
    "google_translate_from_text_file",
    "google_translate_from_html_javascript",
    "google_translate_from_html_xlsxfile",
]


def selenium_chrome_google_translate_text_file(ctx: "RuntimeContext", text_file_path):
    driver = ctx.browser.driver  # Phase H: bind active browser handle
    try:

        if not ctx.browser.google_translate_first_page_loaded:
            selenium_chrome_google_click_cookies_consent_button(ctx)

        driver.get("https://translate.google.com/?sl=%s&tl=%s&op=docs" % (ctx.language.src_lang,ctx.language.dest_lang))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        browse_file_element_xpath = "//label[contains(.,'Browse your computer')]"

        #browse_file_element = WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.XPATH, browse_file_element_xpath)))))

        #safe_click(driver, browse_file_element)

        # Waiting for URL : https://translate.googleusercontent.com/translate_f

        print("Selecting file %s for uploading..." % (text_file_path))
        text_file_element_xpath = "//input[@name='file']"
        text_file_element_xpath = "//input[@id='i37']"
        text_file_element_xpath = "//div[3]/input"
        text_file_element = WebDriverWait(driver, 925).until(EC.presence_of_element_located((By.XPATH, text_file_element_xpath)))

        text_file_element.send_keys(text_file_path)

        #text_file_translate_button_xpath = "//div[2]/div[2]/button/span"
        text_file_translate_button_xpath = "//div[2]/div/button/span"



        text_file_translate_button = WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.XPATH, text_file_translate_button_xpath)))

        print("Clicking on Translate button...")
        safe_click(driver, text_file_translate_button)

        # Wait for result text translation page to be loaded
        loop_wait_translation_count = 200

        print("Waiting for translation result...")
        while(driver.current_url != 'https://translate.googleusercontent.com/translate_f' and loop_wait_translation_count > 0):
            time.sleep(0.1)
            loop_wait_translation_count = loop_wait_translation_count - 1

        #Wait for page status loaded to be complete
        WebDriverWait(driver, 15).until(lambda driver: driver.execute_script('return document.readyState') == 'complete')

        print("Translation received.")

        #print("loop_wait_translation_count: %d" % (200 - loop_wait_translation_count))
        #print("URL: %s" % (driver.current_url))

        html_translation = driver.page_source
        text_translated_document_str = html_translation.replace('<html><head><meta charset="UTF-8"></head><body><pre>', '')
        text_translated_document_str = text_translated_document_str.replace('</pre></body></html>', '')
        text_translated_document_str = html.unescape(text_translated_document_str)

        ctx.docx.translation_array = text_translated_document_str.split('\n')

        text_translated_document_str_nb_lines = len(ctx.docx.translation_array)

        #print ("text_translated_document_str_nb_linestext_translated_document_str_nb_lines: %s" % text_translated_document_str_nb_lines)
        print ("docxfile_table_number_of_phrases: %s" % ctx.docx.docxfile_table_number_of_phrases)

        if ctx.docx.docxfile_table_number_of_phrases == text_translated_document_str_nb_lines:
            #print("OK, we got the right number of translated lines !")
            pass
        else:
            print("oups ! we got %s translated lines out of %s" % (text_translated_document_str_nb_lines, ctx.docx.docxfile_table_number_of_phrases))
            translation_succeded = False

        #print("text_translated_document_str:")
        #print(text_translated_document_str)

    except Exception:
        print("Error getting google translation from text file.")
        var = traceback.format_exc()
        print(var)
        raise TranslationFailure(
            "Google file-mode (textfile) translation failed — see traceback above",
            reason="google_file_mode_error",
        )
    return ctx.docx.translation_array


def selenium_chrome_google_translate_html_javascript_file(ctx: "RuntimeContext", html_file_path):
    # Phase H: bind the active browser driver into a local name. The
    # function reassigns `driver` later (line ~1485, recovery branch),
    # which makes Python treat `driver` as local for the entire body —
    # without this seed read, every earlier `driver.get(...)` raised
    # UnboundLocalError. After a successful reassign we mirror the new
    # handle back to ctx.browser.driver so downstream calls see it.
    driver = ctx.browser.driver

    html_file_path_escaped = html_file_path.replace('#','%23')
    file_url = 'file://' + html_file_path_escaped

    nb_retry = 3

    while nb_retry > 0:
        nb_retry = nb_retry -1
        try:
            driver.get(file_url)

            print("Reading translation")

            try:
                scrollHeight = driver.execute_script("return document.body.scrollHeight")
                innerHeight = driver.execute_script("return window.innerHeight")
                bar = progressbar.ProgressBar(max_value=scrollHeight)
                bar.update(0)
            except Exception:
                var = traceback.format_exc()
                print(var)

            paragraphs = driver.find_elements(by=By.XPATH, value='//p[@class="translation"]')

            # PROGRESS milestones for the Google-javascript path. The block
            # loop in runner.py emits 25 / 50 / 75 by block, but this code
            # path never goes through the runner — without these emits the
            # UI would jump from "10" (backend started) straight to "100".
            _gj_total = max(1, len(paragraphs))
            _gj_progress_emitted: set = set()

            try:

                # How to detect a paragraph is translated is that it has the string below
                #translated_substring_old = '<font style="vertical-align: inherit;">'
                #translated_substring_new = '<font dir="auto" style="vertical-align: inherit;"><font dir="auto" style="vertical-align: inherit;">'
                re_translated_substring = re.compile('^[ \t\r\n]{0,}<font ')
                scroll_offset_paragraph = 60

                for index, paragraph in enumerate(paragraphs, start=1):
                    # Emit PROGRESS markers proportional to paragraph progress.
                    _pct = int((index / _gj_total) * 100)
                    for _m in (15, 30, 50, 75, 90):
                        if _pct >= _m and _m not in _gj_progress_emitted:
                            print(f"PROGRESS:{_m}", flush=True)
                            _gj_progress_emitted.add(_m)

                    #input("Time out here next line ")
                    viewport_top = driver.execute_script("return window.pageYOffset;")
                    viewport_bottom = viewport_top + driver.execute_script("return window.innerHeight;")

                    # Get the coordinates of the element
                    element_top = paragraph.location['y']
                    element_bottom = element_top + paragraph.size['height']

                    paragraph_html = paragraph.get_attribute('innerHTML')
                    #print(f"{paragraph_html}")

                    location = paragraph.location
                    x = location['x']
                    y = location['y']
                    scroll_position = location['y'] - scroll_offset_paragraph

                    wait_translation_sleep_sec = 0.05

                    # or viewport_top <= element_bottom <= viewport_bottom
                    if viewport_top <= element_top <= viewport_bottom:
                        #print("The element is displayed at the current scroll position.")
                        pass
                    else:
                        #print("The element is not displayed at the current scroll position.")
                        try:
                            driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                            time.sleep(wait_translation_sleep_sec)
                            #print("The element should NOW be displayed at the current scroll position.")
                        except Exception as e:
                            #Ignore and continue if there is an error
                            #print(f"Error scrolling paragraph {index}: {str(e)}")
                            pass

                    # Wait until the translation is available

                    wait_translation_max_sleep_sec = 30
                    loop_wait_translation_count = wait_translation_max_sleep_sec / wait_translation_sleep_sec
                    match_translated_tag = re_translated_substring.match(paragraph_html)
                    while not match_translated_tag and loop_wait_translation_count > 0:
                        #print(f"Sleeping in Paragraph {index}")
                        time.sleep(wait_translation_sleep_sec)
                        paragraph_html = paragraph.get_attribute('innerHTML')
                        match_translated_tag = re_translated_substring.match(paragraph_html)
                        #print(f"\n{paragraph_html}\n")
                        loop_wait_translation_count = loop_wait_translation_count - 1

                    try:
                        bar.update(scroll_position + scroll_offset_paragraph)
                    except Exception:  # Ignore progressbar errors at the end
                        pass
            except Exception:
                var = traceback.format_exc()
                print(var)

            bar.update(scrollHeight)
            progressbar.streams.flush()
            bar.finish()

            # Read translation from HTML
            html_translation = driver.page_source
            #soup = BeautifulSoup(html_translation)
            soup = BeautifulSoup(html_translation, features="lxml")
            pTags = soup.find_all('p', {'class':"translation"})
            ctx.docx.translation_array = []
            for pTranstlation in pTags:
                pData = pTranstlation.text
                if ctx.language.dest_lang.lower() == 'fa':
                    from machine_translate_docx.cli import my_hazm_normalizer
                    pData =  my_hazm_normalizer.normalize(text=pData)
                ctx.docx.translation_array.append(pData)

            return (ctx.docx.translation_array)

        except Exception:
            var = traceback.format_exc()
            print(var)


            print("Here do something exit with session failed ")

            ctx.browser.chrome_options = Options()
            ctx.browser.chrome_options.add_argument("--disable-web-security")
            ctx.browser.chrome_options.add_argument("--disable-xss-auditor")
            ctx.browser.chrome_options.add_argument("--log-level=3")  # fatal
            ctx.browser.chrome_options.add_argument("--lang=en-GB")
            ctx.browser.chrome_options.add_argument("--password-store=basic")

            if not ctx.flags.showbrowser:
                ctx.browser.chrome_options.add_argument("--headless")

            from machine_translate_docx.cli import numrows
            docxfile_table_number_of_lines = numrows
            if ctx.flags.use_api or ctx.flags.splitonly:
                print("\nCreating a new browser for stats")

                service = Service()
                driver = webdriver.Chrome(service=service, options=ctx.browser.chrome_options)
                ctx.browser.driver = driver  # mirror new handle back into ctx


# method to get the downloaded file name
# function to wait for download to finish and then rename the latest downloaded file
def get_last_downloaded_file_path():
    # Phase H: lazy-bind cli's module-level `driver` global (mirrored
    # from ctx.browser.driver by _sync_globals_from_ctx). The inner
    # function closes over this local.
    from machine_translate_docx.cli import driver
    # function to wait for all chrome downloads to finish
    def chrome_downloads(drv):
        if not "chrome://downloads" in drv.current_url: # if 'chrome downloads' is not current tab
            drv.execute_script("window.open('');") # open a new tab
            drv.switch_to.window(driver.window_handles[1]) # switch to the new tab
            drv.get("chrome://downloads/") # navigate to chrome downloads
        dld_file_paths = drv.execute_script("""
            return document.querySelector('downloads-manager')
            .shadowRoot.querySelector('#downloadsList')
            .items.filter(e => e.state === 'COMPLETE')
            .map(e => e.filePath || e.file_path || e.fileUrl || e.file_url);
            """)
        print("dld_file_paths=%s" % (dld_file_paths))
        #input("dld_file_paths press enter")
        return dld_file_paths
    # wait for all the downloads to be completed
    dld_file_paths = []
    while len(dld_file_paths) == 0:
        dld_file_paths = chrome_downloads(driver)
        print("len dld_file_paths=%d" % (len(dld_file_paths)))
        print("res dld_file_paths=%s" % (dld_file_paths))
        #input("Opened download status page")
        #WebDriverWait(driver, 120, 1).until(chrome_downloads) # returns list of downloaded file paths)
    # Close the current tab (chrome downloads)
    if "chrome://downloads" in driver.current_url:
        driver.close()
    # Switch back to original tab
    driver.switch_to.window(driver.window_handles[0])
    # get latest downloaded file name and path
    dlFilename = dld_file_paths[0] # latest downloaded file from the list
    # wait till downloaded file appears in download directory
    time_to_wait = 20 # adjust timeout as per your needs
    time_counter = 0
    while not os.path.isfile(dlFilename):
        print ("We have dlFilename=%s" % (dlFilename))
        time.sleep(5)
        time_counter += 1
        if time_counter > time_to_wait:
            break
    # rename the downloaded file
    print("dlFilename=%s" %(dlFilename))
    return dlFilename
    #shutil.move(dlFilename, os.path.join(download_dir,newFilename))
    return


def selenium_chrome_google_translate_xlsx_file(ctx: "RuntimeContext", xlsx_file_path):
    driver = ctx.browser.driver  # Phase H: bind active browser handle
    try:

        if not ctx.browser.google_translate_first_page_loaded:
            selenium_chrome_google_click_cookies_consent_button(ctx)

        driver.get("https://translate.google.com/?sl=%s&tl=%s&op=docs" % (ctx.language.src_lang,ctx.language.dest_lang))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        browse_file_element_xpath = "//label[contains(.,'Browse your computer')]"

        #browse_file_element = WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.XPATH, browse_file_element_xpath)))))

        #safe_click(driver, browse_file_element)

        # Waiting for URL : https://translate.googleusercontent.com/translate_f

        print("Selecting file %s for uploading..." % (xlsx_file_path))
        xlsx_file_element_xpath = "//input[@name='file']"
        xlsx_file_element_xpath = "//input[@id='i37']"
        #xlsx_file_element_xpath = "//span[contains(.,'Browse your computer')]"
        #xlsx_file_element_xpath = '//button[normalize-space()="Browse your computer"]'
        xlsx_file_element_xpath = "//div[3]/input"
        xlsx_file_element = WebDriverWait(driver, 925).until(EC.presence_of_element_located((By.XPATH, xlsx_file_element_xpath)))

        xlsx_file_element.send_keys(xlsx_file_path)
        #input(" HERE : xlsx_file_path")

        #xlsx_file_translate_button_xpath = "//div[2]/div[2]/button/span"
        xlsx_file_translate_button_xpath = "//div[2]/div/button/span"

        xlsx_file_translate_button = WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.XPATH, xlsx_file_translate_button_xpath)))

        print("Clicking on Translate button...")
        #input("BEFORE : xlsx_file_translate_button")
        safe_click(driver, xlsx_file_translate_button)
        #input(" HERE : xlsx_file_translate_button")

        # Wait for result text translation page to be loaded
        loop_wait_translation_count = 200


        res_downloaded_xlsx_translation  = False
        print("Waiting for translation result...")
        while(driver.current_url != 'https://translate.googleusercontent.com/translate_f' and loop_wait_translation_count > 0 and res_downloaded_xlsx_translation == False):
            time.sleep(0.1)
            loop_wait_translation_count = loop_wait_translation_count - 1

            if ("https://www.google.com/sorry" in driver.current_url):
                print("We found a CAPTCHA window")
                from machine_translate_docx.cli import silent
                if not silent:
                    input("Press enter after solving CAPTCHA")
                else:
                    # In silent mode (e.g. spawned by local_launcher.py)
                    # there's no user to solve the CAPTCHA — fail fast
                    # instead of hanging the launcher subprocess pipe.
                    raise RuntimeError("Google CAPTCHA encountered in silent mode — cannot proceed without user interaction")

            download_button_xpath = '//button[normalize-space()="Download translation"]'
            download_button_xpath = '//div[2]/div/button/span'
            download_button_xpath = '//div/button[2]/span[2]'


            try:
                download_button = WebDriverWait(driver, 0.1).until(EC.presence_of_element_located((By.XPATH, download_button_xpath)))
                safe_click(driver, download_button)
                print("We found a download button")
                print("Waiting for download to finish")
                downloaded_xlsx_translation_path = get_last_downloaded_file_path()
                if len(downloaded_xlsx_translation_path) > 0:
                    print("downloaded_xlsx_translation_path=%s" %(downloaded_xlsx_translation_path))
                    res_downloaded_xlsx_translation = True

            except Exception:
                pass

        if res_downloaded_xlsx_translation:
            print("Translation xlsx file downloaded at : %s" %(downloaded_xlsx_translation_path))
            #input("Press enter")

        #input("After download button")
        #Wait for page status loaded to be complete
        WebDriverWait(driver, 10).until(EC.presence_of_element_located(driver.execute_script('return document.readyState') == 'complete'))

        print("Translation received.")
        #input("HERE AGAIN .")

        #print("loop_wait_translation_count: %d" % (200 - loop_wait_translation_count))
        #print("URL: %s" % (driver.current_url))

        html_translation = driver.page_source
        print("html_translation")
        print(html_translation)
        print("\n________________\nhtml_to_text")
        print("BeautifulSoup to text:")
        soup = BeautifulSoup(html_translation, features="lxml")
        soup = BeautifulSoup(html_translation)
        tdTag = soup.find_all("td")
        ctx.docx.translation_array = []
        for td in tdTag:
            pData = td.text
            ctx.docx.translation_array.append(td.text)
            #res = soup.get_text()
            print(pData)
        #input("after pData")
        print(ctx.docx.translation_array)
        print("__________________________")

        # text_translated_document_str = html_translation.replace('<html><head></head><body><pre>', '')
        # text_translated_document_str = text_translated_document_str.replace('</pre></body></html>', '')
        # text_translated_document_str = html.unescape(text_translated_document_str)

        #ctx.docx.translation_array = text_translated_document_str.split('\n')

        text_translated_document_str_nb_lines = len(ctx.docx.translation_array)

        #print ("text_translated_document_str_nb_linestext_translated_document_str_nb_lines: %s" % text_translated_document_str_nb_lines)
        print ("docxfile_table_number_of_phrases: %s" % ctx.docx.docxfile_table_number_of_phrases)

        if ctx.docx.docxfile_table_number_of_phrases == text_translated_document_str_nb_lines:
            #print("OK, we got the right number of translated lines !")
            pass
        else:
            print("oups ! we got %s translated lines out of %s" % (text_translated_document_str_nb_lines, ctx.docx.docxfile_table_number_of_phrases))
            translation_succeded = False

        #print("text_translated_document_str:")
        #print(text_translated_document_str)

    except Exception:
        print("Error getting google translation from text file.")
        var = traceback.format_exc()
        print(var)
        sys.exit(8)
    return ctx.docx.translation_array


def generate_html_file_from_phrases_for_google_translate_javascript(ctx: "RuntimeContext"):
    from machine_translate_docx.cli import (
        dest_lang,
        dest_lang_name,
        docx_file_name,
        from_text_by_phrase_separator_table,
        from_text_table,
        src_lang,
        src_lang_name,
        word_file_to_translate,
        xlsxreplacefile,
        xtm,
    )
    #input("Here")
    print("Generating html page.")

    ctx.docx.docxfile_table_number_of_phrases = 0
    html_to_translate = '''<html lang=%s >
<head>
  <meta charset="UTF-8">
  <title>machine-translate-docx - %s - %s</title>
</head>
<body>
<h3 translate="no">%s - %s</h3>
<p lang=%s translate="yes" id="%s">%s</p>
<table border=1 CELLPADDING=5 CELLSPACING=0>
<tr><td translate="no">Line No</td><td translate="no">%s<td translate="no">%s</td></tr>
''' % (src_lang, docx_file_name, dest_lang_name, docx_file_name, dest_lang_name, src_lang_name, dest_lang_name, dest_lang_name, src_lang_name, dest_lang_name)

    for i, line in enumerate(from_text_table):
        item = from_text_by_phrase_separator_table[i]
        item.strip()

        item_searched_and_replaced_before = item

        if item_searched_and_replaced_before != '':
            if xlsxreplacefile is not None:
                #if xtm.wb is not None:
                if xtm.wb is not None:
                    #print("%d/%d" % (i, word_translation_table_length))
                    #print("Phrase to translate :'%s'\n" % (item.strip()))
                    item_searched_and_replaced_before, nb_searched_and_replaced_before = xtm.search_and_replace_text('before', item, count=False)
                    if item_searched_and_replaced_before.strip() == '' or item_searched_and_replaced_before is None:
                        continue

        item_html_escaped = html.escape(item_searched_and_replaced_before.strip())

        if item_searched_and_replaced_before != '':
            ctx.docx.docxfile_table_number_of_phrases += 1
            html_to_translate = html_to_translate + '''
<tr>
    <td>%s</td>
    <td><p id="phrase_%s_%s" lang="%s" translate="no" class="source">%s</p></td>
    <td id="%s"><p id="phrase_%s_%s" lang=%s class="translation">%s</td>
</tr>
''' % (i+1, i, src_lang, src_lang, item_html_escaped, i, i, dest_lang, src_lang, item_html_escaped)
    html_to_translate = html_to_translate + '''
</table>
<div id="google_translate_element"></div>

<script type="text/javascript">
function googleTranslateElementInit() {
  new google.translate.TranslateElement({pageLanguage: '%s'}, 'google_translate_element');
}
</script>
<script>
    function googleTranslateElementInit() {
        new google.translate.TranslateElement({pageLanguage: '%s', includedLanguages: '%s', autoDisplay: true}, 'google_translate_element');
        var a = document.querySelector("#google_translate_element select");
        a.selectedIndex=1;
        a.dispatchEvent(new Event('change'));
    }
</script>

<script type = "text/javascript">
window.onload = function(){
        var a = document.querySelector("#google_translate_element select");
        a.selectedIndex.value = '%s';
		//document.querySelector('#google_translate_element select').value = '%s';
        a.dispatchEvent(new Event('change'));
}
</script>

<script type="text/javascript" src="https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>
</body>
''' % (src_lang, src_lang, dest_lang,dest_lang,dest_lang)
    #print (html_to_translate)
    try:
        if(platform.system() == "Darwin"):
            # Write to TMPDIR or /tmp folder
            try:
                tmpdir = os.environ['TMPDIR']
                if(tmpdir is None or tmpdir == ""):
                    tmpdir = '/tmp/'
            except Exception:
                tmpdir = '/tmp/'
            html_file_path = tmpdir + docx_file_name + '.' + str(os.getpid()) + '.' + dest_lang + '.html'
        else:
            # Windows, write to file at the same location
            html_file_path = os.path.abspath(os.path.expanduser(os.path.expandvars(word_file_to_translate))) + '.' + str(os.getpid()) + '.' + dest_lang + '.html'

        print(f"Writing temporary html file to : {html_file_path}")
        html_file_to_translate = open(html_file_path, 'w', encoding='utf-8')
        html_file_to_translate.write(html_to_translate)
        html_file_to_translate.close()
        #print("HTML FILE WRITTEN !")
    except Exception:
        var = traceback.format_exc()
        print(var)


def generate_text_file_from_phrases(ctx: "RuntimeContext", text_file_path):
    from machine_translate_docx.cli import (
        from_text_table,
        xlsxreplacefile,
        xtm,
    )
    ctx.docx.docxfile_table_number_of_phrases = 0
    print("Generating text file for google translation...")
    #if xtm.wb is not None:
    if xtm is not None:
        print("Replacing text before using excel file...\n")
    text_to_translate = ''
    text_to_translate_array = []

    for i, line in enumerate(from_text_table):
        item = ctx.docx.from_text_by_phrase_separator_table[i]
        item = item.strip()

        item_searched_and_replaced_before = item

        if item_searched_and_replaced_before != '':
            if xlsxreplacefile is not None:
                #if xtm.wb is not None:
                if xtm.wb is not None:
                    #print("%d/%d" % (i, word_translation_table_length))
                    #print("Phrase to translate :'%s'\n" % (item.strip()))
                    item_searched_and_replaced_before, nb_searched_and_replaced_before = xtm.search_and_replace_text('before', item)
                    if item_searched_and_replaced_before.strip() == '' or item_searched_and_replaced_before is None:
                        continue

        if item_searched_and_replaced_before != '':
            #text_to_translate = text_to_translate + '''%s
#''' % (item)
            text_to_translate_array.append(item_searched_and_replaced_before)
            ctx.docx.docxfile_table_number_of_phrases = ctx.docx.docxfile_table_number_of_phrases + 1
    #print (text_to_translate)
    #print (text_to_translate_array)

    len_text_to_translate_array = len(text_to_translate_array)
    #print("len(text_to_translate_array)=%d" % (len(text_to_translate_array)))

    for index in range(len(text_to_translate_array)):
        #print("%d : '%s'" % (index, text_to_translate_array[index]))
        if index == (len_text_to_translate_array - 1):
            text_to_translate = text_to_translate + '%s' % (text_to_translate_array[index])
        else:
            text_to_translate = text_to_translate + '%s\n' % (text_to_translate_array[index])

    #print("text_to_translate=\n%s" % (text_to_translate))
    try:
        #text_file_path = docx_file_name + '.txt'
        text_file_to_translate = open(text_file_path, 'w', encoding='utf-8')
        text_file_to_translate.write(text_to_translate)
        text_file_to_translate.close()
    except Exception:
        var = traceback.format_exc()
        print(var)


def generate_xlsx_file_from_phrases(ctx: "RuntimeContext", xlsx_file_path):
    from machine_translate_docx.cli import (
        from_text_table,
        silent,
        xlsxreplacefile,
        xtm,
    )
    ctx.docx.docxfile_table_number_of_phrases = 0
    print("Generating xlsx file for google translation...")
    #if xtm.wb is not None:
    if xtm is not None:
        print("Replacing xlsx before using excel file...\n")
    text_to_translate = ''
    text_to_translate_array = []

    for i, line in enumerate(from_text_table):
        item = ctx.docx.from_text_by_phrase_separator_table[i]
        item = item.strip()

        item_searched_and_replaced_before = item

        if item_searched_and_replaced_before != '':
            if xlsxreplacefile is not None:
                #if xtm.wb is not None:
                if xtm.wb is not None:
                    #print("%d/%d" % (i, word_translation_table_length))
                    #print("Phrase to translate :'%s'\n" % (item.strip()))
                    item_searched_and_replaced_before, nb_searched_and_replaced_before = xtm.search_and_replace_text('before', item)
                    if item_searched_and_replaced_before.strip() == '' or item_searched_and_replaced_before is None:
                        continue

        if item_searched_and_replaced_before != '':
            #text_to_translate = text_to_translate + '''%s
            #''' % (item)
            text_to_translate_array.append(item_searched_and_replaced_before)
            ctx.docx.docxfile_table_number_of_phrases = ctx.docx.docxfile_table_number_of_phrases + 1
    #print (text_to_translate)
    #print (text_to_translate_array)

    len_text_to_translate_array = len(text_to_translate_array)
    #print("len(text_to_translate_array)=%d" % (len(text_to_translate_array)))

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "English"
    except Exception:
        print ("Error creating empty xlsx workbook")
        var = traceback.format_exc()
        print("ERROR: %s" % (var))
        self.wb = None
        self.ws = None
        if not silent:
            input("Enter to close program")
        else:
            print("Program ended with errors")
        sys.exit(13)

    index_current_row = 1
    max_col_length = 0
    for index in range(len(text_to_translate_array)):
        ws.cell(row=index_current_row, column=1, value=text_to_translate_array[index])
        if len(text_to_translate_array[index]) > max_col_length:
            max_col_length = len(text_to_translate_array[index])
        index_current_row = index_current_row + 1

    ws.column_dimensions['A'].width = max_col_length + 1000

    file_saved = 0
    while file_saved == 0:
        try:
            wb.save(xlsx_file_path)
            print ("Excel XLSX english text to translate file \"%s\" saved..." %(xlsx_file_path))
            file_saved=1
        except Exception:
            var = traceback.format_exc()
            print(var)
            if not silent:
                txt_readline = input("\n\nERROR: File saving failed. Please close microsoft excel or other program and press enter to save the xlsx document.\n")
            else:
                # No user to dismiss the prompt; back off briefly and
                # retry the loop instead of hanging the launcher pipe.
                time.sleep(2)


def google_translate_from_text_file(ctx: "RuntimeContext"):
    from machine_translate_docx.cli import docx_file_name
    #ctx.flags.word_file_to_translate
    text_file_path = docx_file_name + '.txt'
    text_file_full_path = os.path.realpath(text_file_path)
    #print("text_file_full_path=%s" % text_file_full_path)
    generate_text_file_from_phrases(ctx, text_file_full_path)
    #input("There")
    #input("Here, press enter:")
    print("Starting translation in google using text file...")
    ctx.docx.translation_array = selenium_chrome_google_translate_text_file(ctx, text_file_full_path)
    try:
        os.remove(text_file_path)
        pass
    except Exception:
        pass


def google_translate_from_html_javascript(ctx: "RuntimeContext"):
    from machine_translate_docx.cli import html_file_path
    #input("There")
    #input("Here, press enter:")
    print("Starting translation in google using html file...")

    generate_html_file_from_phrases_for_google_translate_javascript(ctx)

    ctx.docx.translation_array = selenium_chrome_google_translate_html_javascript_file(ctx, html_file_path)

    try:
        #input("before remove html file")
        os.remove(html_file_path)
        pass
    except Exception:
        pass

    return ctx.docx.translation_array


def google_translate_from_html_xlsxfile(ctx: "RuntimeContext"):
    xlsx_file_path = ctx.flags.word_file_to_translate + '.xlsx'
    xlsx_file_full_path = os.path.realpath(xlsx_file_path)
    #print("text_file_full_path=%s" % text_file_full_path)
    generate_xlsx_file_from_phrases(ctx, xlsx_file_full_path)
    #input("There")
    #input("Here, press enter:")
    print("Starting translation in google using text file...")
    ctx.docx.translation_array = selenium_chrome_google_translate_xlsx_file(ctx, xlsx_file_full_path)
    try:
        os.remove(xlsx_file_full_path)
        pass
    except Exception:
        pass
