"""Stats + reporting helpers extracted from `cli.py` (Sprint D, 2026-05-16).

Owns the end-of-run reporting cluster that does not touch the docx itself:

* :func:`local_time_offset` — small pure helper returning the local timezone
  offset (hours from UTC). Used by both the run-summary printer and the
  PHP-side usage report.
* :func:`run_statistics` (D-A.4) — driver-side statistics collection +
  opt-in submission to the HTML usage form. Spawns its own Chrome instance
  in the ``use_api`` / ``splitonly`` branches because those code paths
  don't otherwise need a driver. Honours ``MTD_SKIP_STATS_BROWSER`` to
  short-circuit the entire function — set by the cache refactor's
  launcher basic-split spawn so it doesn't waste a Chrome launch on a
  re-split that won't ship stats.
* :func:`get_robot_usage_comment` (extracted in D-A.5) — HTML report
  builder consumed by the legacy report-back endpoint.

All helpers here are fire-and-forget: a failure inside them never aborts a
translation — the launcher only cares about the docx + sidecar landing on
disk. The outer ``except Exception`` in :func:`run_statistics` and the
``Warning failed to update stats`` print are preserved verbatim from the
legacy body for behaviour parity.
"""
from __future__ import annotations

import json
import os
import platform
import re
import time
import traceback
import xml.dom.minidom
import zipfile
from typing import TYPE_CHECKING
from urllib.parse import urlencode, quote_plus

import json5

if TYPE_CHECKING:
    from .runtime import RuntimeContext


__all__ = [
    "local_time_offset",
    "run_statistics",
    "get_robot_usage_comment",
]


def local_time_offset(t: float | None = None) -> int | float:
    """Return the local timezone offset from UTC in hours.

    Handles DST + the "no DST in this region" case the way the historical
    body did (the inversion in the trailing conditional). Returns ``int``
    when the offset has no fractional part, otherwise ``float``. The
    legacy callers were tolerant of either shape.
    """
    if t is None:
        t = time.time()
    localtimezone = -time.altzone / 3600
    if (localtimezone - int(localtimezone)) == 0:
        localtimezone = int(localtimezone)
    if time.localtime(t).tm_isdst == False or time.daylight != 1:
        localtimezone = -localtimezone
    return localtimezone


def run_statistics(ctx: "RuntimeContext") -> None:
    """End-of-run usage statistics ping.

    Builds a query-string payload from per-run state (ctx fields + a
    handful of cli module globals) and submits it to the HTML stats form
    via a short-lived Chrome session. Best-effort: any failure is caught
    by the outer ``except Exception`` and surfaced as a single
    ``Warning failed to update stats`` line to stdout — the run as a
    whole still succeeds.

    Cache-refactor consumer hook
    ----------------------------
    When ``MTD_SKIP_STATS_BROWSER`` is set in the environment, the
    entire function short-circuits. The launcher's basic-split spawn
    (cache replay path that re-applies a splitter to a cached raw docx)
    sets this so the spawn doesn't pay for a Chrome launch — the
    original translate run already submitted stats for the same docx.

    Phase H bridge
    --------------
    The legacy body read several module-level globals from
    ``machine_translate_docx.cli`` by bare name. Those are lazy-imported
    inside the function (matching the ``docx_io/parse.py:88`` pattern)
    so callers that only need :func:`local_time_offset` don't pay for a
    selenium import at module load time. ``end_time`` and
    ``elapsed_time`` are intentionally NOT lazy-imported: they have
    never been bound as cli module-level names (only as ``_end_time`` /
    ``_elapsed_time`` locals in ``main()``), so bare-name references
    below raise ``NameError`` which is caught by the outer except —
    identical to legacy behaviour. A future cleanup would thread them
    in as kwargs.
    """
    # Cache-refactor consumer hook: skip the whole stats run when the
    # launcher's basic-split spawn doesn't need it.
    if os.environ.get("MTD_SKIP_STATS_BROWSER"):
        return

    # Heavy / driver imports — kept lazy so callers of local_time_offset
    # don't pay for selenium + psutil at module-load time.
    import psutil
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException, WebDriverException

    # 2026-05-16 Sprint D-C slice 6 — read runtime-changing values from
    # ctx instead of bare cli module globals (the Phase H bridge that used
    # to mirror them is gone). Stable values (argparse-time constants,
    # start_time, PROGRAM_VERSION) still come from cli's module namespace.
    from machine_translate_docx.cli import (
        PROGRAM_VERSION,
        dest_font,
        docx_file_name,
        split_translation,
        start_time,
        xlsxreplacefile,
    )
    numrows = ctx.docx.numrows
    xtm    = ctx.docx.xtm
    from .config import get_nested_value_from_json_array

    # Phase H: seed local `driver` so subsequent `driver.get(...)` reads
    # don't UnboundLocalError when the reassign branch is skipped.
    driver = ctx.browser.driver

    statistics_html_statistics_form_url_key = ['statistics', 'html_statistics_form_url']
    statistics_html_statistics_form_url = get_nested_value_from_json_array(ctx.config.json_configuration_array, statistics_html_statistics_form_url_key)

    bool_print_stats = False

    try:
        if ctx.flags.splitonly:
            action = "splitonly"
        else:
            action = "translate"

        docxfile_size = os.path.getsize(ctx.flags.word_file_to_translate)
        if ctx.flags.use_api == True:
            ctx.engine.method = "api"
        elif ctx.engine.method is None or ctx.engine.method == "":
            ctx.engine.method = "web"

        if xlsxreplacefile is not None:
            xlsxreplacefile_splitted = os.path.splitext(os.path.basename(xlsxreplacefile))
            xlsxreplacefile_filename_size = len(xlsxreplacefile_splitted)
            xlsxreplacefile_name = "%s%s" % (xlsxreplacefile_splitted[xlsxreplacefile_filename_size-2], xlsxreplacefile_splitted[xlsxreplacefile_filename_size-1])
        else:
            xlsxreplacefile_name = ""

        if xlsxreplacefile_name != "":
            replacebeforelistsize = xtm.get_sheet_number_lines('before')
            replacebeforelistreplaced = xtm.get_sheet_number_of_replacements('before')
            replaceafterlistsize = xtm.get_sheet_number_lines('after')
            replaceafterlistreplaced = xtm.get_sheet_number_of_replacements('after')
            donotsplitlistsize = xtm.get_sheet_number_lines('keep_on_same_line')
            donotsplitfound = xtm.get_sheet_number_of_do_not_split_match('keep_on_same_line')
        else:
            replacebeforelistsize = ""
            replacebeforelistreplaced = ""
            replaceafterlistsize = ""
            replaceafterlistreplaced = ""
            donotsplitlistsize = ""
            donotsplitfound = ""

        platform_uname = platform.uname()
        platform_system = platform.system()
        platform_node = platform.node()
        platform_release = platform.release()
        platform_version = platform.version()
        platform_machine = platform.machine()
        platform_processor = platform.processor()

        cpu_count = psutil.cpu_count()
        mem_total = psutil.virtual_memory().total

        cost_google_translate = 20 * ctx.docx.docxfile_table_number_of_characters / 1000000

        local_time_offset_str = local_time_offset()

        docxfile_page_count = None
        try:
            document = zipfile.ZipFile(ctx.flags.word_file_to_translate)
            dxml = document.read('docProps/app.xml')
            uglyXml = xml.dom.minidom.parseString(dxml)
            docxfile_page_count = uglyXml.getElementsByTagName('Pages')[0].childNodes[0].nodeValue
        except Exception:
            if bool_print_stats:
                print("Unable to get number of pages from document. You can ignore this.")

        try:
            archive = zipfile.ZipFile("myDocxOrPptxFile.docx", "r")
            ms_data = archive.read("docProps/app.xml")
            archive.close()
            app_xml = ms_data.decode("utf-8")

            regex = r"<(Pages|Slides)>(\d)</(Pages|Slides)>"

            matches = re.findall(regex, app_xml, re.MULTILINE)
            match = matches[0] if matches[0:] else [0, 0]
            page_count = match[1]
        except Exception:
            if bool_print_stats:
                print("Unable to get number of pages from document. You can ignore this.")

        if bool_print_stats:
            print("Statistics:")
            print("program_version: %s" % (PROGRAM_VERSION))
            print("client_ip: %s" % (ctx.flags.client_ip))

            print("docxfile: %s" % (ctx.flags.word_file_to_translate))
            print("action: %s" % (action))
            print("destlang_code: %s" % (ctx.language.dest_lang))
            print("destlang_name: %s" % (ctx.language.dest_lang_name))
            print("docxfile: %s" % (docx_file_name))
            print("docxfile_page_count: %s" % docxfile_page_count)
            print("docxfile_size: %s" % (docxfile_size))
            print("docxfile_table_number_of_lines: %s" % (numrows))
            print("docxfile_table_number_of_phrases: %s" % (ctx.docx.docxfile_table_number_of_phrases))
            print("docxfile_table_number_of_words: %s" % (ctx.docx.docxfile_table_number_of_words))
            print("docxfile_table_number_of_characters: %s" % (ctx.docx.docxfile_table_number_of_characters))
            print("engine: %s" % (ctx.engine.engine))
            print("xlsxreplacefile: %s" % (xlsxreplacefile_name))
            print("destfont: %s" % (dest_font))
            print("splitonly: %s" % (ctx.flags.splitonly))
            print("split_translation: %s" % (split_translation))
            print("showbrowser: %s" % (ctx.flags.showbrowser))
            print("start_time: %s" % (start_time))
            print("end_time: %s" % (end_time))
            print("elapsed_time: %s" % ((elapsed_time)))


            if xlsxreplacefile_name != "":
                print("replacebeforelistsize: %s" % (replacebeforelistsize))
                print("replacebeforelistreplaced: %s" % (replacebeforelistreplaced))
                print("replaceafterlistsize: %s" % (replaceafterlistsize))
                print("replaceafterlistreplaced: %s" % (replaceafterlistreplaced))
                print("donotsplitlistsize: %s" % (donotsplitlistsize))
                print("donotsplitfound: %s" % (donotsplitfound))

            print("str_uname : %s" % (str(platform_uname)))
            print("platform_system: %s" % (platform_system))
            print("platform_node: %s" % (platform_node))
            print("platform_release: %s" % (platform_release))
            print("platform_version: %s" % (platform_version))
            print("platform_machine: %s" % (platform_machine))
            print("platform_processor: %s" % (platform_processor))
            print("cpu_count: %s" % (cpu_count))
            print("mem_total: %s" % (mem_total))
            print("local_time_offset: %s" % (local_time_offset_str))
            print(f"cost_google_translate: {cost_google_translate:.2f}$")
            print("")

        ctx.browser.chrome_options = Options()
        ctx.browser.chrome_options.add_argument("--disable-web-security")
        ctx.browser.chrome_options.add_argument("--disable-xss-auditor")
        ctx.browser.chrome_options.add_argument("--log-level=3")  # fatal
        ctx.browser.chrome_options.add_argument("--lang=en-GB")
        ctx.browser.chrome_options.add_argument("--password-store=basic")

        if not ctx.flags.showbrowser:
            ctx.browser.chrome_options.add_argument("--headless")

        docxfile_table_number_of_lines = numrows
        if ctx.flags.use_api or ctx.flags.splitonly:
            print("\nCreating a new browser for stats")

            service = Service()
            driver = webdriver.Chrome(service=service, options=ctx.browser.chrome_options)
            ctx.browser.driver = driver  # mirror new handle back into ctx

        query_params = {
            "program_version" : PROGRAM_VERSION,
            "engine" : ctx.engine.engine,
            "engine_method" : ctx.engine.method,
            "action" : action,
            "destlang_code" : ctx.language.dest_lang,
            "destlang_name" : ctx.language.dest_lang_name,
            "docxfile_size" : docxfile_size,
            "docxfile_table_number_of_lines" : docxfile_table_number_of_lines,
            "docxfile_table_number_of_phrases" : ctx.docx.docxfile_table_number_of_phrases,
            "docxfile_table_number_of_words" : ctx.docx.docxfile_table_number_of_words,
            "docxfile_table_number_of_characters" : ctx.docx.docxfile_table_number_of_characters,
            "xlsxreplacefile" : xlsxreplacefile_name,
            "destfont" : dest_font,
            "split_translation" : split_translation,
            "showbrowser" : ctx.flags.showbrowser,
            "start_time" : start_time,
            "end_time" : end_time,
            "elapsed_time" : elapsed_time,
            "replacebeforelistsize" : replacebeforelistsize,
            "replacebeforelistreplaced" : replacebeforelistreplaced,
            "replaceafterlistsize" : replaceafterlistsize,
            "replaceafterlistreplaced" : replaceafterlistreplaced,
            "replaceafterlistsize" : replaceafterlistsize,
            "replaceafterlistreplaced" : replaceafterlistreplaced,
            "donotsplitlistsize" : donotsplitlistsize,
            "donotsplitfound" : donotsplitfound,
            "platform_uname" : platform_uname,
            "platform_system" : platform_system,
            "platform_release" : platform_release,
            "platform_version" : platform_version,
            "platform_machine" : platform_machine,
            "platform_processor" : platform_processor,
            "cpu_count" : cpu_count,
            "platform_processor" : platform_processor,
            "mem_total" : mem_total,
            "elapsed_time" : elapsed_time,
            "local_time_offset" : local_time_offset_str,
            "docxfile_page_count" : docxfile_page_count,
            "platform_node" : platform_node,
            "docxfile" : docx_file_name,
            "client_ip" : ctx.flags.client_ip
        }

        base_url = statistics_html_statistics_form_url
        encoded_params = urlencode(query_params, quote_via=quote_plus)
        url = f"{base_url}?{encoded_params}"

        try:
            driver.set_page_load_timeout(12)  # 12 seconds
            driver.get(url)

            submit_stats_element = "//input[@value='Submit']"
            try:
                submit_stats_button = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.XPATH, submit_stats_element)))
                submit_stats_button.submit()
                submited_div_element = "//div[@id='form_post_submitted']"
                submited_div = WebDriverWait(driver, 4).until(EC.presence_of_element_located((By.XPATH, submited_div_element)))
            except Exception:
                print("Warning failed to update stats, you can ignore this.")
        except TimeoutException:
            print(f"Timeout: Page did not load within 10 seconds: {url}")
        except WebDriverException as e:
            print(f"WebDriver error: {e}")
    except Exception:
        print("Warning failed to update stats, you can ignore this...")


def get_robot_usage_comment(ctx: "RuntimeContext") -> None:
    """End-of-run "available updates" check.

    Navigates the active Selenium driver to the version-checker page,
    submits a JSON blob describing the current run, scrapes the
    rendered comment, and prints it to stdout. Best-effort: any
    failure (no driver, network error, missing DOM element) is caught
    and surfaced as a single ``Warning failed to get available
    updates status`` line — the run as a whole still succeeds.

    Cache-refactor consumer hook
    ----------------------------
    When ``MTD_SKIP_STATS_BROWSER`` is set in the environment, the
    entire function short-circuits — the launcher's basic-split
    spawn skips the version-checker ping for the same reason it
    skips :func:`run_statistics`.

    Behaviour preservation
    ----------------------
    The body has long-standing dead code after a ``return 0`` on the
    success path (the second half of the function, including the
    ``forms.gle`` form-fill section). Extraction preserves it
    verbatim so any future un-deadening lands an exact restore.
    The bare-name ``end_time`` / ``elapsed_time`` reads share the
    same NameError-then-caught-by-outer-except pattern documented on
    :func:`run_statistics`.
    """
    # Cache-refactor consumer hook: skip the whole comment retrieval
    # when the launcher's basic-split spawn doesn't need it.
    if os.environ.get("MTD_SKIP_STATS_BROWSER"):
        return

    # Heavy / driver imports — kept lazy so callers of local_time_offset
    # don't pay for them at module-load time.
    import psutil
    from bs4 import BeautifulSoup
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    # Phase H bridge — pull the cli module globals that the legacy body
    # read by bare name. Same end_time / elapsed_time caveat as
    # run_statistics.
    from machine_translate_docx.cli import (
        PROGRAM_VERSION,
        dest_font,
        docx_file_name,
        numrows,
        split_translation,
        start_time,
        xlsxreplacefile,
        xtm,
    )
    from .config import get_nested_value_from_json_array
    from .selenium_utils import browser_fill_form_field_value, safe_click

    javascript_json_version_checker_url_key = ['version_checker', 'javascript_json_version_checker_url']
    javascript_json_version_checker_url = get_nested_value_from_json_array(ctx.config.json_configuration_array, javascript_json_version_checker_url_key)

    if ctx.flags.use_api == True:
        ctx.engine.method = "api"
    elif ctx.engine.method is None or ctx.engine.method == "":
        ctx.engine.method = "web"

    if xlsxreplacefile is not None:
        xlsxreplacefile_splitted = os.path.splitext(os.path.basename(xlsxreplacefile))
        xlsxreplacefile_filename_size = len(xlsxreplacefile_splitted)
        xlsxreplacefile_name = "%s%s" % (xlsxreplacefile_splitted[xlsxreplacefile_filename_size-2], xlsxreplacefile_splitted[xlsxreplacefile_filename_size-1])
    else:
        xlsxreplacefile_name = ""

    if xlsxreplacefile_name != "":
        replacebeforelistsize = xtm.get_sheet_number_lines('before')
        replacebeforelistreplaced = xtm.get_sheet_number_of_replacements('before')
        replaceafterlistsize = xtm.get_sheet_number_lines('after')
        replaceafterlistreplaced = xtm.get_sheet_number_of_replacements('after')
        donotsplitlistsize = xtm.get_sheet_number_lines('keep_on_same_line')
        donotsplitfound = xtm.get_sheet_number_of_do_not_split_match('keep_on_same_line')
    else:
        replacebeforelistsize = ""
        replacebeforelistreplaced = ""
        replaceafterlistsize = ""
        replaceafterlistreplaced = ""
        donotsplitlistsize = ""
        donotsplitfound = ""


    try:
        ctx.browser.driver.get(javascript_json_version_checker_url)
        bool_print_stats = False

        json_obj = json5.loads("{}")

        json_obj["program_version"] = PROGRAM_VERSION
        json_obj["docxfile"] = ctx.flags.word_file_to_translate

        if ctx.flags.splitonly:
            json_obj['action'] = "splitonly"
        else:
            json_obj['action'] = "translate"

        json_obj["destlang_code"] = ctx.language.dest_lang
        json_obj["destlang_name"] = ctx.language.dest_lang_name
        json_obj["docxfile"] = "%s%s" % (docx_file_name,"'")
        json_obj["docxfile_table_number_of_lines"] = numrows
        json_obj["docxfile_table_number_of_phrases"] = ctx.docx.docxfile_table_number_of_phrases
        json_obj["docxfile_table_number_of_words"] = ctx.docx.docxfile_table_number_of_words
        json_obj["docxfile_table_number_of_characters"] = ctx.docx.docxfile_table_number_of_characters
        json_obj["engine"] = ctx.engine.engine
        json_obj["engine_method"] = ctx.engine.method
        json_obj["xlsxreplacefile"] = xlsxreplacefile_name
        if dest_font is not None:
            json_obj["destfont"] = "%s" % dest_font
        json_obj["splitonly"] = ctx.flags.splitonly
        json_obj["split_translation"] = split_translation
        json_obj["showbrowser"] = ctx.flags.showbrowser
        json_obj["start_time"] = "%s" % start_time
        json_obj["end_time"] = "%s" % end_time
        json_obj["elapsed_time"] = "%s" % elapsed_time

        try:
            docxfile_size = os.path.getsize(ctx.flags.word_file_to_translate)
            json_obj["docxfile_size"] = docxfile_size
            if ctx.flags.use_api == True:
                json_obj['engine_method'] = "api"
            elif ctx.engine.method is None or ctx.engine.method == "":
                json_obj['engine_method'] = "web"

            if xlsxreplacefile is not None:
                xlsxreplacefile_splitted = os.path.splitext(os.path.basename(xlsxreplacefile))
                xlsxreplacefile_filename_size = len(xlsxreplacefile_splitted)
                xlsxreplacefile_name = "%s%s" % (xlsxreplacefile_splitted[xlsxreplacefile_filename_size - 2],
                                                 xlsxreplacefile_splitted[xlsxreplacefile_filename_size - 1])
                json_obj['xlsxreplacefile'] = xlsxreplacefile_name
            else:
                json_obj['xlsxreplacefile'] = ""
                json_obj['xlsxreplacefile_filename_size'] = ""

            if xlsxreplacefile_name != "":
                json_obj['replacebeforelistsize'] = xtm.get_sheet_number_lines('before')
                json_obj['replacebeforelistreplaced'] = xtm.get_sheet_number_of_replacements('before')
                json_obj['replaceafterlistsize'] = xtm.get_sheet_number_lines('after')
                json_obj['replaceafterlistreplaced'] = xtm.get_sheet_number_of_replacements('after')
                json_obj['donotsplitlistsize'] = xtm.get_sheet_number_lines('keep_on_same_line')
                json_obj['donotsplitfound'] = xtm.get_sheet_number_of_do_not_split_match('keep_on_same_line')
            else:
                json_obj['replacebeforelistsize'] = ""
                json_obj['replacebeforelistreplaced'] = ""
                json_obj['replaceafterlistsize'] = ""
                json_obj['replaceafterlistreplaced'] = ""
                json_obj['donotsplitlistsize'] = ""
                json_obj['donotsplitfound'] = ""

            json_obj['platform_uname'] = platform.uname()
            json_obj['platform_system'] =  platform.system()
            json_obj['platform_node'] = platform.node()
            json_obj['platform_release'] = platform.release()
            json_obj['platform_version'] = platform.version()
            json_obj['platform_machine'] = platform.machine()
            json_obj['platform_processor'] = platform.processor()

            json_obj['cpu_count'] = psutil.cpu_count()
            json_obj['mem_total'] = psutil.virtual_memory().total

            cost_google_translate = 20 * ctx.docx.docxfile_table_number_of_characters / 1000000

            local_time_offset_str = local_time_offset()

            docxfile_page_count = None
            try:
                document = zipfile.ZipFile(ctx.flags.word_file_to_translate)
                dxml = document.read('docProps/app.xml')
                uglyXml = xml.dom.minidom.parseString(dxml)
                docxfile_page_count = uglyXml.getElementsByTagName('Pages')[0].childNodes[0].nodeValue
                json_obj['docxfile_page_count'] = docxfile_page_count
            except Exception:
                if bool_print_stats:
                    json_obj['docxfile_page_count'] = ""

            try:
                archive = zipfile.ZipFile("myDocxOrPptxFile.docx", "r")
                ms_data = archive.read("docProps/app.xml")
                archive.close()
                app_xml = ms_data.decode("utf-8")

                regex = r"<(Pages|Slides)>(\d)</(Pages|Slides)>"

                matches = re.findall(regex, app_xml, re.MULTILINE)
                match = matches[0] if matches[0:] else [0, 0]
                page_count = match[1]
                json_obj['docxfile_page_count'] = page_count
            except Exception:
                if bool_print_stats:
                    print("Unable to get number of pages from document. You can ignore this.")

            print("\n-------------------------------")
            print("Checking for program updates...")
            print("-------------------------------\n")

            element_json_robot = WebDriverWait(ctx.browser.driver, 1).until(
                    EC.presence_of_element_located((By.ID, "json_robot")))
            ctx.browser.driver.execute_script("arguments[0].innerText = arguments[1]", element_json_robot, json.dumps(json_obj))

            element_submit = WebDriverWait(ctx.browser.driver, 1).until(
                    EC.presence_of_element_located((By.ID, "submit")))
            safe_click(ctx.browser.driver, element_submit)
            ctx.browser.driver.execute_script("arguments[0].click();", element_submit)

            html_translation = ctx.browser.driver.page_source
            soup = BeautifulSoup(html_translation, features="lxml")
            soup_div_text = soup.find('div', id='message_text')
            available_updates_message = ''.join(map(str, soup_div_text.text))

            try:
                soup_div_needs_update = soup.find('div', id='needs_update')
                str_needs_update = ''.join(map(str, soup_div_needs_update.text))
            except Exception:
                pass

            if available_updates_message != "":
                print (''.join(map(str, soup_div_text.text)))
                print("\n-------------------------------")

            return 0;
            try:
                print(ctx.browser.driver.capabilities['browserVersion'])
            except Exception:
                pass
            print(ctx.browser.driver.name)

            if bool_print_stats:
                print("Statistics:")
                print("program_version: %s" % (PROGRAM_VERSION))

                print("docxfile: %s" % (ctx.flags.word_file_to_translate))
                print("action: %s" % (action))
                print("destlang_code: %s" % (ctx.language.dest_lang))
                print("destlang_name: %s" % (ctx.language.dest_lang_name))
                print("docxfile: %s" % (docx_file_name))
                print("docxfile_page_count: %s" % docxfile_page_count)
                print("docxfile_size: %s" % (docxfile_size))
                print("docxfile_table_number_of_lines: %s" % (numrows))
                print("docxfile_table_number_of_phrases: %s" % (ctx.docx.docxfile_table_number_of_phrases))
                print("docxfile_table_number_of_words: %s" % (ctx.docx.docxfile_table_number_of_words))
                print("docxfile_table_number_of_characters: %s" % (ctx.docx.docxfile_table_number_of_characters))
                print("engine: %s" % (ctx.engine.engine))
                print("xlsxreplacefile: %s" % (xlsxreplacefile_name))
                print("destfont: %s" % (dest_font))
                print("splitonly: %s" % (ctx.flags.splitonly))
                print("split_translation: %s" % (split_translation))
                print("showbrowser: %s" % (ctx.flags.showbrowser))
                print("start_time: %s" % (start_time))
                print("end_time: %s" % (end_time))
                print("elapsed_time: %s" % ((elapsed_time)))

                if xlsxreplacefile_name != "":
                    print("replacebeforelistsize: %s" % (replacebeforelistsize))
                    print("replacebeforelistreplaced: %s" % (replacebeforelistreplaced))
                    print("replaceafterlistsize: %s" % (replaceafterlistsize))
                    print("replaceafterlistreplaced: %s" % (replaceafterlistreplaced))
                    print("donotsplitlistsize: %s" % (donotsplitlistsize))
                    print("donotsplitfound: %s" % (donotsplitfound))

                print("str_uname : %s" % (str(platform_uname)))
                print("platform_system: %s" % (platform_system))
                print("platform_node: %s" % (platform_node))
                print("platform_release: %s" % (platform_release))
                print("platform_version: %s" % (platform_version))
                print("platform_machine: %s" % (platform_machine))
                print("platform_processor: %s" % (platform_processor))
                print("cpu_count: %s" % (cpu_count))
                print("mem_total: %s" % (mem_total))
                print("local_time_offset: %s" % (local_time_offset_str))
                print(f"cost_google_translate: {cost_google_translate:.2f}$")
                print("")

            chrome_options = Options()
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-xss-auditor")
            chrome_options.add_argument("--log-level=3")  # fatal
            chrome_options.add_argument("--lang=en-GB")
            chrome_options.add_argument("--password-store=basic")

            ctx.browser.driver.get("https://forms.gle/YeYYUYY5SNo6MKkB8")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(1) .whsOnd", "REMOTE_ADDR")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(2) .whsOnd", "country_name")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(3) .whsOnd", "remote_location_text")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(4) .whsOnd", "HTTP_USER_AGENT")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(5) .whsOnd", "program_version")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(6) .whsOnd", "docxfile")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(7) .whsOnd", "docxfile_page_count")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(8) .whsOnd", "docxfile_size")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(9) .whsOnd", "docxfile_table_number_of_lines")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(10) .whsOnd", "docxfile_table_number_of_words")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(11) .whsOnd", "docxfile_table_number_of_characters")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(12) .whsOnd", "action")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(13) .whsOnd", "destlang_code")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(14) .whsOnd", "destlang_name")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(15) .whsOnd", "engine")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(16) .whsOnd", "engine_method")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(17) .whsOnd", "xlsxreplacefile")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(18) .whsOnd", "destfont")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(19) .whsOnd", "split_translation")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(20) .whsOnd", "splitonly")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(21) .whsOnd", "showbrowser")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(22) .whsOnd", "server_time")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(23) .whsOnd", "start_time")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(24) .whsOnd", "end_time")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(25) .whsOnd", "elapsed_time")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(26) .whsOnd", "replacebeforelistsize")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(27) .whsOnd", "replacebeforelistreplaced")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(28) .whsOnd", "replaceafterlistsize")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(29) .whsOnd", "replaceafterlistreplaced")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(30) .whsOnd", "donotsplitlistsize")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(31) .whsOnd", "donotsplitfound")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(32) .whsOnd", "platform_uname")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(33) .whsOnd", "platform_system")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(34) .whsOnd", "platform_node")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(35) .whsOnd", "platform_release")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(36) .whsOnd", "platform_version")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(37) .whsOnd", "platform_machine")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(38) .whsOnd", "platform_processor")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(39) .whsOnd", "cpu_count")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(40) .whsOnd", "mem_total")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(41) .whsOnd", "local_time_offset")
            browser_fill_form_field_value(ctx, ".Qr7Oae:nth-child(42) .whsOnd", "docxfile_table_number_of_phrases")

            if not ctx.flags.showbrowser:
                chrome_options.add_argument("--headless")

            docxfile_table_number_of_lines = numrows
            if ctx.flags.use_api or ctx.flags.splitonly:
                print("\nCreating a new browser for stats")

                service = Service()
                ctx.browser.driver = webdriver.Chrome(service=service, options=chrome_options)

            query_params = {
                "program_version": PROGRAM_VERSION,
                "engine": ctx.engine.engine,
                "engine_method": ctx.engine.method,
                "action": action,
                "destlang_code": ctx.language.dest_lang,
                "destlang_name": ctx.language.dest_lang_name,
                "docxfile_size": docxfile_size,
                "docxfile_table_number_of_lines": docxfile_table_number_of_lines,
                "docxfile_table_number_of_phrases": ctx.docx.docxfile_table_number_of_phrases,
                "docxfile_table_number_of_words": ctx.docx.docxfile_table_number_of_words,
                "docxfile_table_number_of_characters": ctx.docx.docxfile_table_number_of_characters,
                "xlsxreplacefile": xlsxreplacefile_name,
                "destfont": dest_font,
                "split_translation": split_translation,
                "showbrowser": ctx.flags.showbrowser,
                "start_time": start_time,
                "end_time": end_time,
                "elapsed_time": elapsed_time,
                "replacebeforelistsize": replacebeforelistsize,
                "replacebeforelistreplaced": replacebeforelistreplaced,
                "replaceafterlistsize": replaceafterlistsize,
                "replaceafterlistreplaced": replaceafterlistreplaced,
                "replaceafterlistsize": replaceafterlistsize,
                "replaceafterlistreplaced": replaceafterlistreplaced,
                "donotsplitlistsize": donotsplitlistsize,
                "donotsplitfound": donotsplitfound,
                "platform_uname": platform_uname,
                "platform_system": platform_system,
                "platform_release": platform_release,
                "platform_version": platform_version,
                "platform_machine": platform_machine,
                "platform_processor": platform_processor,
                "cpu_count": cpu_count,
                "platform_processor": platform_processor,
                "mem_total": mem_total,
                "elapsed_time": elapsed_time,
                "local_time_offset": local_time_offset_str,
                "docxfile_page_count": docxfile_page_count,
                "platform_node": platform_node,
                "docxfile": docx_file_name
            }

            base_url = javascript_json_version_checker_url
            encoded_params = urlencode(query_params, quote_via=quote_plus)
            url = f"{base_url}?{encoded_params}"

            ctx.browser.driver.get(url)

            submit_stats_element = "//input[@value='Submit']"
            try:
                submit_stats_button = WebDriverWait(ctx.browser.driver, 1).until(
                    EC.presence_of_element_located((By.XPATH, submit_stats_element)))
                submit_stats_button.submit()
                submited_div_element = "//div[@id='form_post_submitted']"
                submited_div = WebDriverWait(ctx.browser.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, submited_div_element)))
                print("statistics updated")
            except Exception:
                print("Warning failed to get available updates status, you can ignore this.")

        except Exception:
            print("Warning failed to get available updates status, you can ignore this.")

    except Exception:
        var = traceback.format_exc()
        print("Warning failed to get available updates status, you can ignore this.")
