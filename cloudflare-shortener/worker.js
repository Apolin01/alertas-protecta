/**
 * Acortador de links propio para Protecta Peru — corre en Cloudflare Workers.
 *
 * Endpoints:
 *   POST /create   { "url": "https://..." }  (requiere header Authorization: Bearer <API_TOKEN>)
 *                  -> { "short_url": "https://<tu-worker>.workers.dev/<code>" }
 *   GET  /<code>   -> redirect 302 directo a la URL original (sin vista previa)
 *
 * Requiere un KV Namespace llamado LINKS y una variable/secret API_TOKEN
 * configurados en el dashboard del Worker (ver README.md en esta carpeta).
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.slice(1); // sin la barra inicial

    if (request.method === "POST" && path === "create") {
      const auth = request.headers.get("Authorization") || "";
      if (auth !== `Bearer ${env.API_TOKEN}`) {
        return new Response("Unauthorized", { status: 401 });
      }

      let body;
      try {
        body = await request.json();
      } catch (e) {
        return new Response("Invalid JSON", { status: 400 });
      }

      const longUrl = body.url;
      if (!longUrl || !longUrl.startsWith("http")) {
        return new Response("Invalid url", { status: 400 });
      }

      const code = generateCode();
      await env.LINKS.put(code, longUrl);

      return new Response(JSON.stringify({ short_url: `${url.origin}/${code}` }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    if (request.method === "GET" && path) {
      const longUrl = await env.LINKS.get(path);
      if (longUrl) {
        return Response.redirect(longUrl, 302);
      }
      return new Response("Not found", { status: 404 });
    }

    return new Response("OK — acortador de Protecta Peru activo", { status: 200 });
  },
};

function generateCode(len = 6) {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let code = "";
  for (let i = 0; i < len; i++) {
    code += chars[Math.floor(Math.random() * chars.length)];
  }
  return code;
}
