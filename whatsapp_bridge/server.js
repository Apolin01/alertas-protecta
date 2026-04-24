
const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    isJidGroup,
    downloadMediaMessage,
} = require("@whiskeysockets/baileys");
const { Boom } = require("@hapi/boom");
const express  = require("express");
const QRCode   = require("qrcode");
const fs       = require("fs");
const path     = require("path");
const pino     = require("pino");

// ─────────────────────────────────────────────
// CONFIGURACION
// ─────────────────────────────────────────────
const PORT       = process.env.PORT || 3000;
const AUTH_TOKEN = process.env.BRIDGE_TOKEN || "protecta2026";
const DATA_PATH  = process.env.WA_DATA_PATH || "/app";
const AUTH_DIR   = path.join(DATA_PATH, ".wwebjs_auth", "baileys_auth");
const CACHE_FILE = path.join(DATA_PATH, ".wwebjs_auth", "groupcache.json");

const GROUP_MAP = {
    "Antamina":                     "GII - Antamina - Protecta Perú",
    "Bechtel / Newmont":            "GII - Bechtel - Protecta Perú",
    "Clientes Sur":                 "GII - Agro sur - Protecta Perú",
    "Clientes Norte":               "GII - Agro norte - Protecta Perú",
    "Agricola Santa Azul":          "GII - Agro norte - Agrícola Santa azul - Protecta Perú",
    "Pisco":                        "GII - Pisco - Protecta Perú",
    "Coyuntura Nacional":           "GII - Coyuntura política nacional - Protecta Perú",
    "Agricola Huarmey":             "GII - Agro norte - Protecta Perú",
    "Agricola 3P":                  "GII - Agro norte - Protecta Perú",
    "Agricola Chapi":               "GII - Agro sur - Protecta Perú",
    "Campos Andino":                "GII - Agro norte - Protecta Perú",
    "Campos del Sur":               "GII - Agro sur - Protecta Perú",
    "Don Ricardo":                  "GII - Agro sur - Protecta Perú",
    "Hortifrut":                    "GII - Agro norte - Protecta Perú",
    "Mission":                      "GII - Agro norte - Protecta Perú",
    "RVR":                          "GII - Agro sur - Protecta Perú",
    "SunFruits":                    "GII - Agro norte - Protecta Perú",
    "Vanguard":                     "GII - Agro sur - Protecta Perú",
    "Uvica":                        "GII - Agro sur - Protecta Perú",
    "Ninguno (Coyuntura Nacional)": "GII - Coyuntura política nacional - Protecta Perú",
};

// ─────────────────────────────────────────────
// CACHE
// ─────────────────────────────────────────────
let groupCache = {};  // "Nombre exacto" → "chatId@g.us"

function loadCacheFromDisk() {
    try {
        if (fs.existsSync(CACHE_FILE)) {
            groupCache = JSON.parse(fs.readFileSync(CACHE_FILE, "utf8"));
            console.log(`[Cache] ${Object.keys(groupCache).length} grupos cargados desde disco.`);
        }
    } catch (e) {
        console.warn("[Cache] No se pudo leer cache:", e.message);
    }
}

function saveCacheToDisk() {
    try {
        fs.mkdirSync(path.dirname(CACHE_FILE), { recursive: true });
        fs.writeFileSync(CACHE_FILE, JSON.stringify(groupCache, null, 2), "utf8");
    } catch (e) {
        console.warn("[Cache] No se pudo guardar cache:", e.message);
    }
}

function printCacheStatus() {
    console.log("\n[Cache] Estado del mapeo:");
    for (const [logical, realName] of Object.entries(GROUP_MAP)) {
        const ok = !!groupCache[realName];
        console.log(`  ${ok ? "✅" : "❌"} ${logical} → "${realName}"`);
    }
}

// ─────────────────────────────────────────────
// INICIO
// ─────────────────────────────────────────────
console.log("─".repeat(50));
console.log(`[Init] DATA_PATH  : ${DATA_PATH}`);
console.log(`[Init] AUTH_DIR   : ${AUTH_DIR}`);
console.log(`[Init] CACHE_FILE : ${CACHE_FILE}`);
console.log(`[Init] Volumen OK : ${fs.existsSync(DATA_PATH) ? "SI" : "NO"}`);
console.log("─".repeat(50));

loadCacheFromDisk();

// ─────────────────────────────────────────────
// BAILEYS
// ─────────────────────────────────────────────
let sock      = null;
let isReady   = false;
let qrBase64  = "";
let reconnectTimer = null;

async function loadGroups() {
    console.log("\n[Cache] Cargando grupos via groupFetchAllParticipating...");
    try {
        const groups = await sock.groupFetchAllParticipating();
        let added = 0;
        for (const [id, meta] of Object.entries(groups)) {
            if (!groupCache[meta.subject]) {
                groupCache[meta.subject] = id;
                added++;
            }
        }
        if (added > 0) saveCacheToDisk();
        console.log(`[Cache] ${Object.keys(groups).length} grupos en WA. ${added} nuevos en cache.`);
        printCacheStatus();
    } catch (e) {
        console.error("[Cache] Error cargando grupos:", e.message);
        if (Object.keys(groupCache).length > 0) {
            console.log("[Cache] Usando cache previo del disco.");
            printCacheStatus();
        }
    }
}

async function startSock() {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion();
    console.log(`[Baileys] Versión WA: ${version.join(".")}`);

    sock = makeWASocket({
        version,
        auth: state,
        printQRInTerminal: false,
        logger: pino({ level: "silent" }),
        browser: ["Protecta Bridge", "Chrome", "1.0"],
        connectTimeoutMs: 60000,
        keepAliveIntervalMs: 30000,
        retryRequestDelayMs: 2000,
    });

    sock.ev.on("creds.update", saveCreds);

    sock.ev.on("connection.update", async ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            console.log("\n[QR] Nuevo QR. Abre /qr en el navegador.");
            try { qrBase64 = await QRCode.toDataURL(qr); } catch (_) {}
        }

        if (connection === "close") {
            isReady = false;
            groupCache = {};
            loadCacheFromDisk();
            const code = new Boom(lastDisconnect?.error)?.output?.statusCode;
            const reason = DisconnectReason[code] || code;
            console.log(`❌ Desconectado (${reason})`);

            if (code === DisconnectReason.loggedOut || code === DisconnectReason.badSession) {
                console.log(`Sesión inválida (${reason}). Limpiando auth dir y reconectando para nuevo QR...`);
                try { fs.rmSync(AUTH_DIR, { recursive: true, force: true }); } catch (_) {}
                fs.mkdirSync(AUTH_DIR, { recursive: true });
                if (reconnectTimer) clearTimeout(reconnectTimer);
                reconnectTimer = setTimeout(startSock, 3000);
                return;
            }
            console.log("Reconectando en 5s...");
            if (reconnectTimer) clearTimeout(reconnectTimer);
            reconnectTimer = setTimeout(startSock, 5000);

        } else if (connection === "open") {
            console.log("\n✅ WhatsApp conectado (Baileys).");
            isReady  = true;
            qrBase64 = "";
            await loadGroups();
        }
    });

    // Capturar grupos desde mensajes entrantes/salientes
    sock.ev.on("messages.upsert", async ({ messages }) => {
        for (const msg of messages) {
            const jid = msg.key.remoteJid;
            if (!jid || !isJidGroup(jid)) continue;
            if (Object.values(groupCache).includes(jid)) continue;

            try {
                const meta = await sock.groupMetadata(jid);
                if (meta?.subject) {
                    groupCache[meta.subject] = jid;
                    saveCacheToDisk();
                    console.log(`[Cache] ✅ Grupo capturado: "${meta.subject}" → ${jid}`);
                    const ok = Object.values(GROUP_MAP).filter(n => groupCache[n]).length;
                    console.log(`[Cache] Progreso: ${ok}/${Object.keys(GROUP_MAP).length}`);
                }
            } catch (_) {}
        }
    });
}

startSock().catch(e => console.error("Error iniciando Baileys:", e));

// ─────────────────────────────────────────────
// SERVIDOR HTTP
// ─────────────────────────────────────────────
const app = express();
app.use(express.json({ limit: "10mb" }));

app.get("/", (req, res) => res.send("wa-bridge (Baileys) funcionando"));

app.get("/qr", (req, res) => {
    if (isReady) return res.send(`<html><body style="font-family:Arial;text-align:center;padding:40px"><h2>WhatsApp ya conectado</h2></body></html>`);
    if (!qrBase64) return res.send(`<html><body style="font-family:Arial;text-align:center;padding:40px"><h2>QR aún no disponible</h2><p>Espera unos segundos y recarga.</p></body></html>`);
    return res.send(`<html><body style="font-family:Arial;text-align:center;padding:40px"><h2>Escanea el QR</h2><p>WhatsApp → Dispositivos vinculados → Vincular</p><img src="${qrBase64}" style="max-width:320px"/></body></html>`);
});

// Auth middleware
app.use((req, res, next) => {
    const pub = ["/qr", "/status", "/diagnose", "/favicon.ico", "/"];
    if (pub.includes(req.path)) return next();
    if (req.headers["x-auth-token"] !== AUTH_TOKEN)
        return res.status(401).json({ error: "Token invalido" });
    next();
});

app.get("/status", (req, res) => res.json({
    ready:         isReady,
    groups_cached: Object.keys(groupCache).length,
    mapped_groups: Object.keys(GROUP_MAP).length,
    hora_servidor: new Date().toISOString(),
}));

app.get("/diagnose", (req, res) => res.json({
    isReady,
    groupCache,
    cacheFile:       CACHE_FILE,
    cacheFileExists: fs.existsSync(CACHE_FILE),
    library:         "baileys",
}));

app.get("/groups", (req, res) => {
    if (!isReady) return res.status(503).json({ error: "WhatsApp no listo" });
    res.json({ all_groups: groupCache, mapped: GROUP_MAP });
});

app.post("/set-cache", (req, res) => {
    const { groups } = req.body;
    if (!groups || typeof groups !== "object")
        return res.status(400).json({ error: 'Body: { "groups": { "Nombre": "chatId@g.us" } }' });
    Object.assign(groupCache, groups);
    saveCacheToDisk();
    console.log(`[Cache] ${Object.keys(groups).length} grupos inyectados manualmente.`);
    res.json({ ok: true, total: Object.keys(groupCache).length });
});

app.post("/reload-groups", async (req, res) => {
    if (!isReady) return res.status(503).json({ error: "WhatsApp no listo" });
    await loadGroups();
    res.json({ ok: true, groups: Object.keys(groupCache).length });
});

app.post("/send", async (req, res) => {
    const { group_name, message, image_url } = req.body;
    console.log(`\n[Send] ▶ group="${group_name}" msg=${(message||"").slice(0,60)}...`);

    if (!isReady) {
        console.error("[Send] ✗ WhatsApp no conectado");
        return res.status(503).json({ error: "WhatsApp no conectado." });
    }

    const realName = GROUP_MAP[group_name];
    if (!realName) {
        console.error(`[Send] ✗ '${group_name}' no en GROUP_MAP`);
        return res.status(404).json({ error: `Grupo '${group_name}' no en GROUP_MAP`, available: Object.keys(GROUP_MAP) });
    }

    const chatId = groupCache[realName];
    if (!chatId) {
        console.error(`[Send] ✗ Sin chatId para "${realName}". Cache: ${Object.keys(groupCache).length} grupos`);
        return res.status(404).json({ error: `Grupo "${realName}" no en cache. Envía un mensaje al grupo desde tu celular.` });
    }

    console.log(`[Send] chatId="${chatId}"`);

    try {
        if (image_url && image_url.startsWith("data:")) {
            const [header, data] = image_url.split(",");
            const mimetype = header.split(":")[1].split(";")[0];
            const buffer   = Buffer.from(data, "base64");
            await sock.sendMessage(chatId, { image: buffer, mimetype, caption: message });
            console.log(`✅ [imagen] → "${realName}"`);
        } else {
            await sock.sendMessage(chatId, { text: message });
            console.log(`✅ [texto] → "${realName}"`);
        }
        return res.json({ ok: true, group: realName });
    } catch (err) {
        console.error(`❌ Error enviando a "${realName}":`, err.message);
        return res.status(500).json({ error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`\n🚀 Bridge HTTP en http://localhost:${PORT}`);
    console.log(`   Token: ${AUTH_TOKEN}\n`);
});
