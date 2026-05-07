const express = require("express");
const multer = require("multer");
const fs = require("fs").promises;
const { spawn } = require("cross-spawn");
const path = require("path");
const bodyParser = require("body-parser");
const { access } = require("fs");
const http = require("http");
const cron = require("cron");
const iconv = require('iconv-lite');
const psList = require("ps-list");
const fs2 = require("fs");

const app = express();
app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());

// ── In-memory job store ────────────────────────────────────────────────────────
// { jobId → { status: "pending"|"done"|"error", filename, error, createdAt } }
const jobs = new Map();

function generateJobId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function handleProcessCompletion(code) {
    console.log(`Child process exited with code ${code}`);
}

// ── Multer storage ─────────────────────────────────────────────────────────────
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, "uploads/");
    },
    filename: (req, file, cb) => {
        const originalNameBuffer = Buffer.from(file.originalname, 'binary');
        const decodedName = iconv.decode(originalNameBuffer, 'utf-8');
        const uniqueName = Buffer.from(
            `${new Date().getTime()}-${decodedName}`.replace(/（/g, '(').replace(/）/g, ')'),
            'utf-8'
        ).toString();
        cb(null, uniqueName);
    },
    fileFilter: (req, file, cb) => {
        if (path.extname(file.originalname) === ".docx") {
            cb(null, true);
        } else {
            cb(new Error("Only .docx files are allowed."));
        }
    },
});

const upload = multer({ storage });

const uploadsDirectory = path.resolve(__dirname, "uploads");

// ── Cron: cleanup old files and expired jobs ───────────────────────────────────
const job = new cron.CronJob('*/1 * * * *', () => {
    console.log("Start cron");
    deleteFilesOlderThanAnHour();
    cleanupOldJobs();
});
job.start();

async function deleteFilesOlderThanAnHour() {
    const currentDate = new Date();
    const directory = "uploads";
    try {
        const files = await fs.readdir(directory);
        for (const file of files) {
            const filePath = path.join(directory, file);
            const stats = await fs.stat(filePath);
            const elapsedTime = currentDate - stats.birthtime;
            if (elapsedTime > 60 * 60 * 1000) {
                await fs.unlink(filePath);
                console.log(`File ${file} deleted.`);
            }
        }
    } catch (e) {
        console.error(`Cron cleanup error: ${e.message}`);
    }
}

function cleanupOldJobs() {
    const now = Date.now();
    for (const [id, j] of jobs) {
        // Remove completed/failed jobs older than 2 hours
        if (j.status !== "pending" && now - j.createdAt > 2 * 60 * 60 * 1000) {
            jobs.delete(id);
        }
        // Mark stuck pending jobs (no process exit after 50 min) as timed out
        if (j.status === "pending" && now - j.createdAt > 50 * 60 * 1000) {
            jobs.set(id, { ...j, status: "error", error: "Translation timed out on server." });
        }
    }
}

// ── Logging helpers ────────────────────────────────────────────────────────────
const logsDirectory = path.join(__dirname, 'logs');
if (!fs2.existsSync(logsDirectory)) {
    fs2.mkdirSync(logsDirectory, { recursive: true });
}

function formatDateTime() {
    return new Date().toISOString();
}

function logCommand(command, args, exitCode = null) {
    const logFilePath = path.join(logsDirectory, 'command_log.txt');
    const exitLogFilePath = path.join(logsDirectory, 'command_exit_log.txt');
    const dateTime = formatDateTime();
    const exitCodeLog = exitCode !== null ? `; Exit Code: ${exitCode}` : '';
    const logEntry = `${dateTime} :  ${command} ${args.join(' ')}${exitCodeLog}\n`;

    fs2.appendFile(logFilePath, logEntry, (err) => {
        if (err) console.error(`Failed to log command: ${err.message}`);
        else console.log(`Command logged: ${dateTime} ${args.join(' ')}`);
    });

    if (exitCode !== null) {
        fs2.appendFile(exitLogFilePath, logEntry, (err) => {
            if (err) console.error(`Failed to log exit command: ${err.message}`);
        });
    }
}

// ── Process limits ─────────────────────────────────────────────────────────────
const MAX_USER_PROCESSES = 2;
const MAX_TOTAL_PROCESSES = 4;

// ── Language DB ────────────────────────────────────────────────────────────────
const languageDb = [
    { name: "Arabic",                  value: "ar",      flag: "ARA", deepl: false },
    { name: "Bulgarian",               value: "bg",      flag: "BUL", deepl: true  },
    { name: "Czech",                   value: "cs",      flag: "CZE", deepl: true  },
    { name: "English",                 value: "en",      flag: "ENG", deepl: false },
    { name: "Persian",                 value: "fa",      flag: "PER", deepl: false },
    { name: "Chinese (Simplified)",    value: "zh-CN",   flag: "CHI", deepl: true  },
    { name: "Chinese (Simplified)",    value: "zh-hans", flag: "CHI", deepl: true  },
    { name: "Chinese (Traditional)",   value: "zh-TW",   flag: "CHI", deepl: true  },
    { name: "Chinese (Traditional)",   value: "zh-hant", flag: "CHI", deepl: true  },
    { name: "French",                  value: "fr",      flag: "FRE", deepl: true  },
    { name: "German",                  value: "de",      flag: "GER", deepl: true  },
    { name: "Hindi",                   value: "hi",      flag: "HIN", deepl: false },
    { name: "Hungarian",               value: "hu",      flag: "HUN", deepl: true  },
    { name: "Indonesian",              value: "id",      flag: "IND", deepl: true  },
    { name: "Italian",                 value: "it",      flag: "ITA", deepl: true  },
    { name: "Japanese",                value: "ja",      flag: "JPN", deepl: true  },
    { name: "Korean",                  value: "ko",      flag: "KOR", deepl: true  },
    { name: "Malay",                   value: "ms",      flag: "MAY", deepl: false },
    { name: "Mongolian",               value: "mn",      flag: "MON", deepl: false },
    { name: "Nepali",                  value: "ne",      flag: "NEP", deepl: false },
    { name: "Polish",                  value: "pl",      flag: "POL", deepl: true  },
    { name: "Portuguese",              value: "pt",      flag: "POR", deepl: true  },
    { name: "Portuguese (Brazilian)",  value: "pt-br",   flag: "POR", deepl: true  },
    { name: "Punjabi",                 value: "pa",      flag: "PAN", deepl: false },
    { name: "Romanian",                value: "ro",      flag: "RUM", deepl: true  },
    { name: "Russian",                 value: "ru",      flag: "RUS", deepl: true  },
    { name: "Spanish",                 value: "es",      flag: "SPA", deepl: true  },
    { name: "Telugu",                  value: "te",      flag: "TEL", deepl: false },
    { name: "Thai",                    value: "th",      flag: "THA", deepl: false },
    { name: "Ukrainian",               value: "uk",      flag: "UKR", deepl: true  },
    { name: "Urdu",                    value: "ur",      flag: "URD", deepl: false },
    { name: "Vietnamese",              value: "vi",      flag: "VIE", deepl: true  },
];

// ── Utility: wait for file to appear ──────────────────────────────────────────
const { constants } = require("fs");

const waitForFile = async (filePath, timeout = 2400000, interval = 1000) => {
    const start = Date.now();
    while (true) {
        try {
            await fs.access(filePath, constants.F_OK);
            return true;
        } catch {
            if (Date.now() - start > timeout) {
                throw new Error(`Timeout waiting for file: ${filePath}`);
            }
            await new Promise(res => setTimeout(res, interval));
        }
    }
};

// ── View engine ────────────────────────────────────────────────────────────────
app.set("view engine", "ejs");

// ── GET / ──────────────────────────────────────────────────────────────────────
app.get("/", (req, res) => {
    res.set('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
    res.set('Pragma', 'no-cache');
    res.set('Expires', '0');
    res.render("index");

    const realIp =
        req.headers['x-real-ip'] ||
        req.headers['x-forwarded-for']?.split(',')[0] ||
        req.socket.remoteAddress;
    console.log('Client IP:', realIp);
});

// ── GET /robotscount ───────────────────────────────────────────────────────────
app.get("/robotscount", async (req, res) => {
    try {
        const realIp =
            req.headers["x-real-ip"] ||
            req.headers["x-forwarded-for"]?.split(",")[0] ||
            req.socket.remoteAddress;

        const processes = await psList();
        let allCount = 0;
        let userCount = 0;

        processes.forEach(p => {
            const name = (p.name || "").toLowerCase();
            const cmd  = (p.cmd  || "").toLowerCase();
            const isPython = /^python\d*(\.\d+)*$/.test(name) && cmd.includes("machine-translate-docx.py");
            const isExe    = name === "machine-translate-docx.exe";
            if (isPython || isExe) {
                allCount++;
                if (realIp && cmd.includes(realIp.toLowerCase())) userCount++;
            }
        });

        res.json({ count: { all: allCount, user: userCount } });
    } catch (err) {
        console.error("Error checking processes:", err);
        res.status(500).json({ error: "Failed to check processes" });
    }
});

// ── GET /count ─────────────────────────────────────────────────────────────────
app.get("/count", async (req, res) => {
    try {
        const count = await fs.readFile(path.join(__dirname, "count.txt"), "utf-8");
        res.json({ count });
    } catch (err) {
        console.error(err);
        res.status(500).send("Internal Server Error");
    }
});

// ── GET /status/:jobId  (polling endpoint) ─────────────────────────────────────
app.get("/status/:jobId", (req, res) => {
    const { jobId } = req.params;
    const j = jobs.get(jobId);
    if (!j) return res.status(404).json({ ok: false, status: "not_found" });
    return res.json({
        ok:       true,
        status:   j.status,
        filename: j.filename || null,
        error:    j.error    || null,
    });
});

// ── GET /robots.txt ────────────────────────────────────────────────────────────
app.get('/robots.txt', (req, res) => {
    res.type('text/plain');
    res.send(
`User-agent: *
Disallow: /

# Prevent indexing
Noindex: /
Nofollow: /`
    );
});

// ── POST /upload ───────────────────────────────────────────────────────────────
app.post("/upload", upload.single("file"), async (req, res) => {
    // Short timeout — we return a jobId immediately, no long-poll needed
    req.setTimeout(30000);

    // ── Process-limit check ────────────────────────────────────────────────────
    const realIP =
        req.headers["x-real-ip"] ||
        req.headers["x-forwarded-for"]?.split(",")[0] ||
        req.socket.remoteAddress;

    let allCount = 0;
    let userCount = 0;

    try {
        const processes = await psList();
        for (const p of processes) {
            const name = (p.name || "").toLowerCase();
            const cmd  = (p.cmd  || "").toLowerCase();
            const isPython = /^python\d*(\.\d+)*$/.test(name) && cmd.includes("machine-translate-docx.py");
            const isExe    = name === "machine-translate-docx.exe";
            if (isPython || isExe) {
                allCount++;
                if (realIP && cmd.includes(`--clientip ${realIP.toLowerCase()}`)) userCount++;
            }
        }

        if (userCount >= MAX_USER_PROCESSES) {
            return res.status(200).json({
                ok: false,
                comment: `You already have ${userCount} translations running. Maximum per-user limit is ${MAX_USER_PROCESSES}. Please try later.`,
            });
        }

        if (allCount >= MAX_TOTAL_PROCESSES) {
            return res.status(200).json({
                ok: false,
                comment: `Server is busy with ${allCount} ongoing translations. Maximum total limit is ${MAX_TOTAL_PROCESSES}. Please try later.`,
            });
        }
    } catch (err) {
        console.error("Error checking processes:", err);
    }

    // ── Build command ──────────────────────────────────────────────────────────
    const uploadedFile  = req.file;
    const fileName      = uploadedFile.filename;
    const {
        sourceLanguage,
        targetLanguage,
        translationEngine,
        splitTranslate,
        splitEngine,
        aiModel,
    } = req.body;

    const targetPath = path.join(uploadsDirectory, fileName);

    console.log(`Translating file  : ${fileName}`);
    console.log(`targetLanguage    : ${targetLanguage}`);
    console.log(`translationEngine : ${translationEngine}`);
    console.log(`splitEngine       : ${splitEngine}`);

    function shellEscape(arg) {
        if (!arg) return "''";
        return `'${arg.replace(/'/g, `'\\''`)}'`;
    }

    let fullCommand =
        `source /home/robot/.bashrc; source /home/robot/venv_python311/bin/activate; python3 ` +
        shellEscape('/home/robot/robot-app/machine-translate-docx-main/src/machine-translate-docx.py') + ' ' +
        `--srclang ${shellEscape(sourceLanguage)} ` +
        `--destlang ${shellEscape(targetLanguage)} ` +
        `--engine ${shellEscape(translationEngine)} ` +
        `--docxfile ${shellEscape(targetPath)} ` +
        `-t -q ` +
        (splitTranslate ? ' --split' : '');

    if (translationEngine === 'perplexity') fullCommand += ` --enginemethod webservice `;
    if (splitEngine === 'openai')           fullCommand += ` --splitengine openai `;
    if (translationEngine === 'google')     fullCommand += ` --showbrowser `;
    if (translationEngine === 'chatgpt' || translationEngine === 'chatgpt-polish') {
        console.log('OpenAI engine → --enginemethod api');
        fullCommand += ` --enginemethod 'api' `;
        const resolvedModel = aiModel || 'gpt-5.5';
        fullCommand += ` --aimodel ${shellEscape(resolvedModel)} `;
        console.log(`OpenAI model: ${resolvedModel}`);
    }
    if (translationEngine === 'chatgpt-polish') {
        console.log('Polish pass enabled → --with-polish');
        fullCommand += ` --with-polish `;
    }
    if (realIP && realIP !== '84.46.246.132') {
        fullCommand += ` --clientip ${shellEscape(realIP)} `;
    }

    const fsxlsx = require('fs');
    const destLangEntry = languageDb.find(lang => lang.value === targetLanguage);
    if (destLangEntry) {
        const xlsxFilePath = `/home/robot/robot-app/machine-translate-docx-main/${destLangEntry.name.toLowerCase()}.xlsx`;
        if (fsxlsx.existsSync(xlsxFilePath)) {
            fullCommand += ` --xlsxreplacefile ${shellEscape(xlsxFilePath)} `;
            console.log('Using xlsx file:', xlsxFilePath);
        } else {
            console.log('xlsx file not found:', xlsxFilePath);
        }
    }

    // ── Register job and spawn process ─────────────────────────────────────────
    const jobId = generateJobId();
    jobs.set(jobId, { status: "pending", filename: null, error: null, createdAt: Date.now() });

    const exitMessages = {
        1:   "File not found on the server.",
        2:   "Not a .docx file. Please convert to docx first.",
        3:   "Not a valid docx file. Please convert to docx first.",
        5:   "Error using Google Translate. Please try again later.",
        6:   "Error accepting Google cookie consent.",
        7:   "Error getting Google translation from text file.",
        8:   "Error getting Google translation from Excel file.",
        9:   "Error getting translation from Yandex.",
        11:  "The table does not have the minimum expected 3 columns.",
        12:  "An error occurred during Chrome launch. Please contact support.",
        13:  "Error creating empty xlsx workbook for the search and replace.",
        137: "Server window was closed. Sorry, please try again.",
    };

    const cmd = spawn("gnome-terminal", ["--wait", "--", "bash", "-ic", fullCommand]);

    cmd.stderr.on("data", (data) => {
        console.error(`stderr: ${data.toString()}`);
    });

    cmd.on("close", async (code) => {
        logCommand(fullCommand, [], code);

        // ── Compute expected output filename ────────────────────────────────
        const flag = languageDb.find(lang => lang.value === targetLanguage);
        if (!flag) {
            jobs.set(jobId, { ...jobs.get(jobId), status: "error", error: "Unknown target language." });
            return;
        }

        const fileExtension = 'docx';
        const suffix = `_${flag.flag}.${fileExtension}`;
        const regex  = new RegExp(`_${flag.flag}\\.${fileExtension}$`, 'i');
        let modifiedFileName;
        if (!regex.test(fileName)) {
            modifiedFileName = fileName.replace(new RegExp(`\\.${fileExtension}$`, 'i'), suffix);
        } else {
            modifiedFileName = fileName;
        }

        const newFilePath = path.join(uploadsDirectory, modifiedFileName);

        // ── Handle non-zero exit ────────────────────────────────────────────
        if (code !== 0) {
            console.log(`Process exited with code ${code}`);
            const message = exitMessages[code] || "Unknown error occurred. Please contact support.";
            jobs.set(jobId, { ...jobs.get(jobId), status: "error", error: message });
            return;
        }

        // ── Wait for output file ────────────────────────────────────────────
        try {
            await waitForFile(newFilePath, 2400000, 1000);
        } catch (err) {
            console.error(err.message);
            jobs.set(jobId, { ...jobs.get(jobId), status: "error", error: "Translation output file not found in time." });
            return;
        }

        // ── Verify file accessible ──────────────────────────────────────────
        try {
            await fs.access(newFilePath);
        } catch (e) {
            jobs.set(jobId, { ...jobs.get(jobId), status: "error", error: e.message });
            return;
        }

        // ── Increment global counter ────────────────────────────────────────
        try {
            const count    = await fs.readFile(path.join(__dirname, "count.txt"), "utf-8");
            const newCount = Number(count) + 1;
            await fs.writeFile(path.join(__dirname, "count.txt"), String(newCount), "utf-8");
        } catch (e) {
            console.error("Failed to update count.txt:", e.message);
        }

        // ── Mark job as done ────────────────────────────────────────────────
        const newFilename = modifiedFileName.replace("uploads\\", "");
        console.log(`Job ${jobId} done → ${newFilename}`);
        jobs.set(jobId, { ...jobs.get(jobId), status: "done", filename: newFilename });
    });

    // Safety: send stdin quit after ~16 minutes to avoid zombie terminals
    setTimeout(() => {
        try { cmd.stdin.write("quit\n"); cmd.stdin.end(); } catch (_) {}
    }, 1000000);

    // ── Return jobId immediately ───────────────────────────────────────────────
    return res.status(200).json({ ok: true, jobId });
});

// ── GET /download/:fileName ────────────────────────────────────────────────────
app.get("/download/:fileName", (req, res) => {
    req.setTimeout(9999999);
    res.setTimeout(9999999);

    try {
        const fileName = req.params.fileName;
        console.log("Download request:", fileName);
        console.log("Full URL:", req.url);

        const fileNameParts = fileName.split('-');
        fileNameParts.shift();
        const modifiedFileName = fileNameParts.join('-');
        const filePath = path.join(uploadsDirectory, fileName);

        const encodedFileName = modifiedFileName.replace(/#/g, '%23');
        res.download(filePath, encodedFileName);
    } catch (error) {
        console.error("Error downloading file", error);
        res.status(500).send("Internal Server Error");
    }
});

// ── Start server ───────────────────────────────────────────────────────────────
const startServer = async () => {
    const privateKey  = await fs.readFile('./ssl/private.key',       'utf8');
    const certificate = await fs.readFile('./ssl/certificate.crt',   'utf8');
    const ca          = await fs.readFile('./ssl/ca_bundle.crt',      'utf8');

    const credentials = { key: privateKey, cert: certificate, ca };

    const server = http.createServer(app);
    const portNumber = 3000;
    server.timeout = 9999999;
    server.listen(portNumber, '0.0.0.0', () => {
        console.log(`Server is running on port ${portNumber}`);
        console.log('timeout:', server.timeout);
    });
};

startServer();
