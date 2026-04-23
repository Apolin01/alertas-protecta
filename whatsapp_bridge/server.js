
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
        console.log(`[Cache] ${cachedCount} grupos ya en memoria desde disco — omitiendo getChats() pesado.`);
        // Refrescar en background después de 60s sin bloquear
        setTimeout(() => {
            buildGroupCache().catch(err => console.warn("Refresh cache fallido:", err.message));
        }, 60000);
    } else {
        // Primera vez: cargar grupos (sin cache previo)
        setTimeout(() => {
            buildGroupCache().catch(err => {
                console.error("Error cargando cache inicial:", err.message);
                setTimeout(() => buildGroupCache().catch(e => console.error("Reintento fallido:", e.message)), 30000);
            });
        }, 5000);
    }
});

client.on("disconnected", (reason) => {
    console.log("❌ WhatsApp desconectado:", reason);
    isReady    = false;
    groupCache = {};
});

client.on("auth_failure", (msg) => {
    console.error("❌ Error de autenticacion:", msg);
});

// ─────────────────────────────────────────────
// CACHE DE GRUPOS
// ─────────────────────────────────────────────
let _cacheBuilding = false;

async function buildGroupCache() {
    if (_cacheBuilding) {
        console.log("[Cache] buildGroupCache ya en curso, saltando.");
        return;
    }
    _cacheBuilding = true;
    console.log("\nCargando grupos de WhatsApp...");
    try {
        const chats  = await client.getChats();
        const groups = chats.filter(c => c.isGroup);
        const newCache = {};

        console.log(`\nGrupos encontrados (${groups.length}):`);
        groups.forEach(g => {
            newCache[g.name] = g.id._serialized;
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
        console.log("[Cache] Usando cache previo del disco. Reintentando en 2 min...");
        setTimeout(() => {
            _cacheBuilding = false;
            buildGroupCache().catch(e => console.error("Reintento fallido:", e.message));
        }, 120000);
        return;
    }
    _cacheBuilding = false;
}

async function findGroupChatId(realName) {
    // Buscar en cache primero
    if (groupCache[realName]) return groupCache[realName];

    // Intentar getChats si no está en cache
    console.log(`[Cache] Buscando '${realName}' via getChats...`);
    try {
        const chats = await client.getChats();
        chats.filter(c => c.isGroup).forEach(g => {
            groupCache[g.name] = g.id._serialized;
        });
        saveCacheToDisk();
    } catch (e) {
        console.error("[Cache] getChats fallido en búsqueda:", e.message);
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
    const publicPaths = ["/qr", "/status"];

    if (publicPaths.includes(req.path)) {
        return next();
    }

    if (req.headers["x-auth-token"] !== AUTH_TOKEN) {
        return res.status(401).json({ error: "Token invalido" });
    }

    next();
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

// GET /groups — lista todos los grupos
app.get("/groups", async (req, res) => {
    if (!isReady) return res.status(503).json({ error: "WhatsApp no listo" });
    res.json({
        all_groups: Object.keys(groupCache),
        mapped:     GROUP_MAP,
    });
});

// POST /reload-groups — recarga cache
app.post("/reload-groups", async (req, res) => {
    await buildGroupCache();
    res.json({ ok: true, groups: Object.keys(groupCache).length });
});

// POST /send — envia alerta a un grupo
app.post("/send", async (req, res) => {
    if (!isReady) {
        return res.status(503).json({
            error: "WhatsApp no conectado. Escanea el QR primero."
        });
    }

    const { group_name, message, image_url } = req.body;

    if (!group_name || !message) {
        return res.status(400).json({ error: "group_name y message son requeridos" });
    }

    // Resolver nombre logico → nombre real del grupo
    const realName = GROUP_MAP[group_name];
    if (!realName) {
        return res.status(404).json({
            error: `Grupo logico '${group_name}' no esta en GROUP_MAP`,
            available: Object.keys(GROUP_MAP),
        });
    }

    // Resolver nombre real → chatId (con búsqueda lazy si no está en cache)
    const chatId = await findGroupChatId(realName);
    if (!chatId) {
        return res.status(404).json({
            error: `Grupo '${realName}' no encontrado en WhatsApp`,
            hint:  "Cache aún cargando o nombre incorrecto en GROUP_MAP. Reintenta en 2 min.",
        });
    }

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