
const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");
const express  = require("express");
const QRCode   = require("qrcode");
const axios    = require("axios");
const fs       = require("fs");
const path     = require("path");

// ─────────────────────────────────────────────
// CONFIGURACION
// ─────────────────────────────────────────────
const PORT       = 3000;
const AUTH_TOKEN = "protecta2026";

// Mapeo: nombre logico (config.py) → nombre EXACTO del grupo en WhatsApp
const GROUP_MAP = {
    "Antamina":                    "GII - Antamina - Protecta Perú",
    "Bechtel / Newmont":           "GII - Bechtel - Protecta Perú",
    "Clientes Sur":                "GII - Agro sur - Protecta Perú",
    "Clientes Norte":              "GII - Agro norte - Protecta Perú",
    "Agricola Santa Azul":         "GII - Agro norte - Agrícola Santa azul - Protecta Perú",
    "Pisco":                       "GII - Pisco - Protecta Perú",
    "Coyuntura Nacional":          "GII - Coyuntura política nacional - Protecta Perú",
    // Clientes que van al grupo de su region padre
    "Agricola Huarmey":            "GII - Agro norte - Protecta Perú",
    "Agricola 3P":                 "GII - Agro norte - Protecta Perú",
    "Agricola Chapi":              "GII - Agro sur - Protecta Perú",
    "Campos Andino":               "GII - Agro norte - Protecta Perú",
    "Campos del Sur":              "GII - Agro sur - Protecta Perú",
    "Don Ricardo":                 "GII - Agro sur - Protecta Perú",
    "Hortifrut":                   "GII - Agro norte - Protecta Perú",
    "Mission":                     "GII - Agro norte - Protecta Perú",
    "RVR":                         "GII - Agro sur - Protecta Perú",
    "SunFruits":                   "GII - Agro norte - Protecta Perú",
    "Vanguard":                    "GII - Agro sur - Protecta Perú",
    "Uvica":                       "GII - Agro sur - Protecta Perú",
    "Ninguno (Coyuntura Nacional)":"GII - Coyuntura política nacional - Protecta Perú",
};

// ─────────────────────────────────────────────
// CLIENTE WHATSAPP
// ─────────────────────────────────────────────
// Volumen Railway montado en /app/.wwebjs_auth — LocalAuth crea esa carpeta bajo dataPath
const DATA_PATH = process.env.WA_DATA_PATH || "/app";

const client = new Client({
    authStrategy: new LocalAuth({
        clientId: "railway",
        dataPath: DATA_PATH
    }),
    puppeteer: {
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
        headless: true,
        protocolTimeout: 300000,
        args: [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-zygote",
            "--disable-extensions",
            "--disable-default-apps",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--no-first-run",
            "--mute-audio",
            "--hide-scrollbars",
            "--js-flags=--max-old-space-size=256",
        ],
    },
});

let isReady    = false;
let groupCache = {};  // nombre exacto → chatId
let qrImageBase64 = "";
let lastQrText = "";

const CACHE_FILE = path.join(DATA_PATH, ".wwebjs_auth", "groupcache.json");

function loadCacheFromDisk() {
    try {
        if (fs.existsSync(CACHE_FILE)) {
            groupCache = JSON.parse(fs.readFileSync(CACHE_FILE, "utf8"));
            console.log(`[Cache] ${Object.keys(groupCache).length} grupos cargados desde disco.`);
        }
    } catch (e) {
        console.warn("[Cache] No se pudo leer cache del disco:", e.message);
    }
}

function saveCacheToDisk() {
    try {
        fs.mkdirSync(path.dirname(CACHE_FILE), { recursive: true });
        fs.writeFileSync(CACHE_FILE, JSON.stringify(groupCache, null, 2), "utf8");
        console.log(`[Cache] ${Object.keys(groupCache).length} grupos guardados en disco.`);
    } catch (e) {
        console.warn("[Cache] No se pudo guardar cache:", e.message);
    }
}

// ── Diagnóstico de arranque ───────────────────
console.log("─".repeat(50));
console.log(`[Init] DATA_PATH   : ${DATA_PATH}`);
console.log(`[Init] CACHE_FILE  : ${CACHE_FILE}`);
console.log(`[Init] Volumen OK  : ${fs.existsSync(path.dirname(CACHE_FILE)) ? "SI" : "NO — carpeta no existe"}`);
console.log("─".repeat(50));

loadCacheFromDisk();

client.on("qr", async (qr) => {
    console.log("\nNuevo QR generado. Abre /qr en el navegador.");
    lastQrText = qr;

    try {
        qrImageBase64 = await QRCode.toDataURL(qr);
        console.log("QR disponible en /qr");
    } catch (err) {
        console.error("Error generando imagen QR:", err.message);
    }
});

client.on("ready", () => {
    console.log("\n✅ WhatsApp conectado.");
    isReady = true;
    qrImageBase64 = "";
    lastQrText = "";

    const cachedCount = Object.keys(groupCache).length;
    if (cachedCount > 0) {
        console.log(`[Cache] ${cachedCount} grupos en cache. Listo para enviar.`);
        console.log("[Cache] Grupos disponibles:");
        for (const [logical, realName] of Object.entries(GROUP_MAP)) {
            const ok = !!groupCache[realName];
            console.log(`  ${ok ? "✅" : "❌"} ${logical} → "${realName}"`);
        }
    } else {
        console.log("[Cache] ⚠️  Sin cache. El bridge NO puede enviar hasta que inyectes grupos.");
        console.log("[Cache] Llama: POST /set-cache  con x-auth-token: protecta2026");
    }
});

client.on("disconnected", (reason) => {
    console.log(`❌ WhatsApp desconectado: ${reason}`);
    isReady = false;
    loadCacheFromDisk();
});

// ── Captura automática de grupos desde mensajes entrantes ─────
// Cuando llega cualquier mensaje de un grupo, guardamos su chatId.
// Solo manda un mensaje desde tu celular a cada grupo y el cache se llena solo.
client.on("message_create", async (msg) => {
    const chatId = msg.fromMe ? msg.to : msg.from;
    console.log(`[MsgCreate] fromMe=${msg.fromMe} from=${msg.from} to=${msg.to} → chatId=${chatId}`);

    if (!chatId || !chatId.endsWith("@g.us")) return;
    if (Object.values(groupCache).includes(chatId)) {
        console.log(`[Cache] chatId ${chatId} ya conocido`);
        return;
    }

    try {
        const name = await Promise.race([
            client.pupPage.evaluate((id) => {
                if (!window.Store || !window.Store.Chat) return null;
                const chat = window.Store.Chat.get(id);
                return chat ? (chat.name || chat.formattedTitle || null) : null;
            }, chatId),
            new Promise((_, r) => setTimeout(() => r(new Error("timeout 10s")), 10000))
        ]);

        if (name) {
            groupCache[name] = chatId;
            saveCacheToDisk();
            console.log(`[Cache] ✅ Grupo capturado: "${name}" → ${chatId}`);
            const ok = Object.values(GROUP_MAP).filter(n => groupCache[n]).length;
            console.log(`[Cache] Progreso: ${ok}/${Object.keys(GROUP_MAP).length} grupos mapeados`);
        } else {
            console.log(`[Cache] nombre no encontrado para ${chatId} — guardando por ID`);
            groupCache[chatId] = chatId;
        }
    } catch (e) {
        console.warn(`[Cache] evaluate falló: ${e.message} — guardando chatId directo`);
        groupCache[`group_${chatId}`] = chatId;
        saveCacheToDisk();
    }
});

client.on("message", async (msg) => {
    const chatId = msg.from;
    console.log(`[Msg] from=${msg.from} isGroup=${chatId.endsWith("@g.us")}`);
});

client.on("auth_failure", (msg) => {
    console.error("❌ Error de autenticacion:", msg);
});

// ─────────────────────────────────────────────
// CACHE DE GRUPOS
// ─────────────────────────────────────────────
let _cacheBuilding = false;

async function getGroupsLightweight() {
    // Accede directo al store interno de WA Web — solo extrae name + id,
    // sin serializar chats completos. Mucho más rápido que client.getChats().
    return client.pupPage.evaluate(() => {
        try {
            const models = window.Store && window.Store.Chat
                ? Array.from(window.Store.Chat.models)
                : [];
            return models
                .filter(c => c.isGroup)
                .map(c => ({
                    name: c.name || c.formattedTitle || "",
                    id:   c.id && c.id._serialized ? c.id._serialized : ""
                }))
                .filter(c => c.name && c.id);
        } catch (e) {
            return null;
        }
    });
}

async function buildGroupCache() {
    if (_cacheBuilding) {
        console.log("[Cache] buildGroupCache ya en curso, saltando.");
        return;
    }
    _cacheBuilding = true;
    console.log("\nCargando grupos de WhatsApp (modo ligero)...");
    try {
        const groups = await getGroupsLightweight();

        if (!groups || groups.length === 0) {
            throw new Error("Store vacío o no disponible aún");
        }

        const newCache = {};
        console.log(`\nGrupos encontrados (${groups.length}):`);
        groups.forEach(g => {
            newCache[g.name] = g.id;
            console.log(`  "${g.name}"`);
        });

        groupCache = newCache;
        saveCacheToDisk();

        console.log("\nEstado del mapeo GROUP_MAP:");
        for (const [logical, realName] of Object.entries(GROUP_MAP)) {
            const found = !!groupCache[realName];
            const icon  = found ? "✅" : "❌";
            console.log(`  ${icon} "${logical}" → "${realName}"`);
        }
        console.log("");

    } catch (err) {
        console.error("Error cargando grupos:", err.message);
        console.log("[Cache] Reintentando en 2 min...");
        setTimeout(() => {
            _cacheBuilding = false;
            buildGroupCache().catch(e => console.error("Reintento fallido:", e.message));
        }, 120000);
        return;
    }
    _cacheBuilding = false;
}

async function findGroupChatId(realName) {
    if (groupCache[realName]) return groupCache[realName];

    console.log(`[Cache] '${realName}' no en cache, recargando...`);
    try {
        const groups = await getGroupsLightweight();
        if (groups && groups.length > 0) {
            groups.forEach(g => { groupCache[g.name] = g.id; });
            saveCacheToDisk();
        }
    } catch (e) {
        console.error("[Cache] Búsqueda ligera fallida:", e.message);
    }
    return groupCache[realName] || null;
}

// ─────────────────────────────────────────────
// SERVIDOR HTTP
// ─────────────────────────────────────────────
const app = express();
app.use(express.json({ limit: "10mb" }));


app.get("/", (req, res) => {
    res.send("wa-bridge funcionando");
});

app.get("/qr", (req, res) => {
    if (isReady) {
        return res.send(`
            <html>
              <body style="font-family: Arial; text-align:center; padding:40px;">
                <h2>WhatsApp ya está conectado</h2>
                <p>No necesitas escanear un nuevo QR.</p>
              </body>
            </html>
        `);
    }

    if (!qrImageBase64) {
        return res.send(`
            <html>
              <body style="font-family: Arial; text-align:center; padding:40px;">
                <h2>QR aún no disponible</h2>
                <p>Espera unos segundos y recarga la página.</p>
              </body>
            </html>
        `);
    }

    return res.send(`
        <html>
          <body style="font-family: Arial; text-align:center; padding:40px;">
            <h2>Escanea el QR con WhatsApp</h2>
            <p>WhatsApp → Dispositivos vinculados → Vincular un dispositivo</p>
            <img src="${qrImageBase64}" style="max-width:320px; width:100%;" />
          </body>
        </html>
    `);
});


// Auth middleware
app.use((req, res, next) => {
    const publicPaths = ["/qr", "/status", "/diagnose", "/favicon.ico", "/"];

    if (publicPaths.includes(req.path)) {
        return next();
    }

    if (req.headers["x-auth-token"] !== AUTH_TOKEN) {
        return res.status(401).json({ error: "Token invalido" });
    }

    next();
});

// GET /diagnose — estado interno del bridge
app.get("/diagnose", async (req, res) => {
    const info = {
        isReady,
        groupCache_size: Object.keys(groupCache).length,
        groupCache,
        cacheFile: CACHE_FILE,
        cacheFileExists: fs.existsSync(CACHE_FILE),
    };
    try {
        const store = await Promise.race([
            client.pupPage.evaluate(() => ({
                hasStore:    !!window.Store,
                hasChat:     !!(window.Store && window.Store.Chat),
                chatCount:   window.Store && window.Store.Chat ? window.Store.Chat.models.length : 0,
                groupCount:  window.Store && window.Store.Chat
                    ? Array.from(window.Store.Chat.models).filter(c => c.isGroup).length : 0,
            })),
            new Promise((_, r) => setTimeout(() => r(new Error("timeout 8s")), 8000))
        ]);
        info.store = store;
    } catch (e) {
        info.store_error = e.message;
    }
    res.json(info);
});

// GET /status
app.get("/status", (req, res) => {
    res.json({
        ready:          isReady,
        groups_cached:  Object.keys(groupCache).length,
        mapped_groups:  Object.keys(GROUP_MAP).length,
        hora_servidor:  new Date().toISOString(),
    });
});

// GET /groups — lista todos los grupos con sus chatIds
app.get("/groups", async (req, res) => {
    if (!isReady) return res.status(503).json({ error: "WhatsApp no listo" });
    res.json({
        all_groups: groupCache,   // { "Nombre grupo": "chatId@g.us" }
        mapped:     GROUP_MAP,
    });
});

// POST /set-cache — inyecta chatIds obtenidos del servidor local
// Body: { "groups": { "Nombre exacto grupo": "xxxx@g.us", ... } }
app.post("/set-cache", (req, res) => {
    const { groups } = req.body;
    if (!groups || typeof groups !== "object") {
        return res.status(400).json({ error: 'Body esperado: { "groups": { "Nombre": "chatId@g.us" } }' });
    }
    Object.assign(groupCache, groups);
    saveCacheToDisk();
    console.log(`[Cache] ${Object.keys(groups).length} grupos inyectados. Total: ${Object.keys(groupCache).length}`);
    res.json({ ok: true, total: Object.keys(groupCache).length, groups: groupCache });
});

// POST /reload-groups — recarga cache
app.post("/reload-groups", async (req, res) => {
    await buildGroupCache();
    res.json({ ok: true, groups: Object.keys(groupCache).length });
});

// POST /send — envia alerta a un grupo
app.post("/send", async (req, res) => {
    const { group_name, message, image_url } = req.body;
    console.log(`\n[Send] ▶ group_name="${group_name}" | msg=${(message||"").slice(0,60)}...`);

    if (!isReady) {
        console.error("[Send] ✗ WhatsApp no conectado (isReady=false)");
        return res.status(503).json({
            error: "WhatsApp no conectado. Escanea el QR primero."
        });
    }

    if (!group_name || !message) {
        console.error("[Send] ✗ Faltan campos group_name o message");
        return res.status(400).json({ error: "group_name y message son requeridos" });
    }

    // Resolver nombre logico → nombre real del grupo
    const realName = GROUP_MAP[group_name];
    if (!realName) {
        console.error(`[Send] ✗ '${group_name}' no está en GROUP_MAP. Disponibles: ${Object.keys(GROUP_MAP).join(", ")}`);
        return res.status(404).json({
            error: `Grupo logico '${group_name}' no esta en GROUP_MAP`,
            available: Object.keys(GROUP_MAP),
        });
    }
    console.log(`[Send] Resuelto → "${realName}"`);

    // Resolver nombre real → chatId (con búsqueda lazy si no está en cache)
    const chatId = await findGroupChatId(realName);
    if (!chatId) {
        console.error(`[Send] ✗ chatId no encontrado para "${realName}". Cache actual (${Object.keys(groupCache).length} grupos): ${Object.keys(groupCache).join(", ") || "VACÍO"}`);
        return res.status(404).json({
            error: `Grupo '${realName}' no encontrado en cache`,
            hint:  "Inyecta el cache con POST /set-cache",
            cache_size: Object.keys(groupCache).length,
        });
    }
    console.log(`[Send] chatId="${chatId}"`);


    try {
        let sent_with_image = false;

        if (image_url) {
            try {
                let media;
                if (image_url.startsWith("data:")) {
                    // Base64 enviado desde el scraper (imagen descargada con sesión FB)
                    const [header, data] = image_url.split(",");
                    const mimetype = header.split(":")[1].split(";")[0];
                    media = new MessageMedia(mimetype, data);
                } else if (image_url.startsWith("http")) {
                    // URL pública
                    media = await MessageMedia.fromUrl(image_url, {
                        unsafeMime: true,
                        reqOptions: { timeout: 10000 },
                    });
                }

                if (media) {
                    await client.sendMessage(chatId, media, { caption: message });
                    sent_with_image = true;
                    console.log(`✅ [imagen] → "${realName}"`);
                } else {
                    throw new Error("media no generado");
                }
            } catch (imgErr) {
                console.warn(`⚠️  Imagen fallida (${imgErr.message}), enviando solo texto...`);
                await client.sendMessage(chatId, message);
                console.log(`✅ [texto] → "${realName}"`);
            }
        } else {
            await client.sendMessage(chatId, message);
            console.log(`✅ [texto] → "${realName}"`);
        }

        return res.json({
            ok:         true,
            group:      realName,
            with_image: sent_with_image,
        });

    } catch (err) {
        console.error(`❌ Error enviando a "${realName}":`, err.message);
        return res.status(500).json({ error: err.message });
    }
});

// ─────────────────────────────────────────────
// ARRANCAR
// ─────────────────────────────────────────────
app.listen(PORT, () => {
    console.log(`\n🚀 Bridge HTTP en http://localhost:${PORT}`);
    console.log(`   Token: ${AUTH_TOKEN}`);
    console.log("\nIniciando WhatsApp...\n");
});

client.initialize();