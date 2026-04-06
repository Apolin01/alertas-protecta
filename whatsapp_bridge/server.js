
const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");
const express  = require("express");
const QRCode = require("qrcode");
const axios    = require("axios");

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
const client = new Client({
    authStrategy: new LocalAuth({
        clientId: "railway",
        dataPath: "/tmp/.wwebjs_auth"
    }),
    puppeteer: {
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
        headless: true,
        args: [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-zygote",
            "--single-process",
        ],
    },
});

let isReady    = false;
let groupCache = {};  // nombre exacto → chatId
let qrImageBase64 = "";
let lastQrText = "";

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
    console.log("WhatsApp listo. La cache de grupos se cargará bajo demanda.");
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
async function buildGroupCache() {
    console.log("\nCargando grupos de WhatsApp...");
    try {
        const chats  = await client.getChats();
        const groups = chats.filter(c => c.isGroup);
        groupCache   = {};

        console.log(`\nGrupos encontrados (${groups.length}):`);
        groups.forEach(g => {
            groupCache[g.name] = g.id._serialized;
            console.log(`  "${g.name}"`);
        });

        console.log("\nEstado del mapeo GROUP_MAP:");
        for (const [logical, realName] of Object.entries(GROUP_MAP)) {
            const found = !!groupCache[realName];
            const icon  = found ? "✅" : "❌";
            console.log(`  ${icon} "${logical}" → "${realName}"`);
        }
        console.log("");

    } catch (err) {
        console.error("Error cargando grupos:", err.message);
    }
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

    // Resolver nombre real → chatId
    let chatId = groupCache[realName];
    if (!chatId) {
        // Recargar cache por si el grupo es nuevo
        await buildGroupCache();
        chatId = groupCache[realName];
        if (!chatId) {
            return res.status(404).json({
                error: `Grupo '${realName}' no encontrado en WhatsApp`,
                hint:  "Verifica el nombre exacto en GROUP_MAP. Corre GET /groups para ver todos.",
            });
        }
    }

    try {
        let sent_with_image = false;

        if (image_url && image_url.startsWith("http")) {
            try {
                const media = await MessageMedia.fromUrl(image_url, {
                    unsafeMime: true,
                    reqOptions: { timeout: 10000 },
                });
                await client.sendMessage(chatId, media, { caption: message });
                sent_with_image = true;
                console.log(`✅ [imagen] → "${realName}"`);
            } catch (imgErr) {
                // Si falla la imagen, enviar solo texto
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