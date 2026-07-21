// Webhook de WhatsApp (Meta Cloud API) -> dispara el workflow "Más noticias".
//
// Corre como Cloudflare Worker (gratis). Cuando le escribes cualquier texto al
// número del bot, Meta hace POST aquí; el worker valida que el mensaje sea tuyo
// y dispara un repository_dispatch en GitHub, que ejecuta news_digest.py --more.
// La respuesta llega por el canal de siempre (CallMeBot).
//
// Variables (Settings -> Variables and Secrets del worker):
//   VERIFY_TOKEN  string inventado por ti; el mismo se pega en Meta al conectar
//   APP_SECRET    App Secret de la app de Meta (para validar la firma HMAC)
//   MY_PHONE      tu número sin "+", ej: 56912345678 (solo tú puedes gatillar)
//   GITHUB_REPO   ej: josesubiabre/whatsapp_news
//   GITHUB_TOKEN  fine-grained PAT con permiso Contents: Read and write
//
// Setup completo paso a paso: README.md en esta carpeta.

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 1) Verificación inicial: Meta llama con GET una sola vez al configurar
    //    el webhook y hay que devolverle el challenge.
    if (request.method === "GET") {
      if (
        url.searchParams.get("hub.mode") === "subscribe" &&
        url.searchParams.get("hub.verify_token") === env.VERIFY_TOKEN
      ) {
        return new Response(url.searchParams.get("hub.challenge"), { status: 200 });
      }
      return new Response("forbidden", { status: 403 });
    }

    if (request.method !== "POST") {
      return new Response("method not allowed", { status: 405 });
    }

    const rawBody = await request.text();

    // 2) Firma: Meta manda el HMAC-SHA256 del cuerpo firmado con el App Secret.
    //    Sin firma válida, cualquiera que conozca la URL podría gatillar envíos.
    if (env.APP_SECRET) {
      const signature = request.headers.get("x-hub-signature-256") || "";
      if (!(await validSignature(rawBody, signature, env.APP_SECRET))) {
        return new Response("bad signature", { status: 401 });
      }
    }

    let payload;
    try {
      payload = JSON.parse(rawBody);
    } catch {
      return new Response("bad json", { status: 400 });
    }

    // 3) Extraer mensajes de texto entrantes. Meta también manda estados de
    //    entrega/lectura por este mismo webhook; se ignoran.
    const messages = (payload.entry || [])
      .flatMap((e) => e.changes || [])
      .flatMap((c) => (c.value && c.value.messages) || [])
      .filter((m) => m.type === "text");

    // Solo reaccionar a MIS mensajes ("from" viene sin el "+").
    const mine = messages.filter((m) => m.from === env.MY_PHONE);

    // 4) Cualquier texto tuyo dispara el workflow (cada mensaje = una tanda
    //    de noticias extra; el historial evita repetidas entre tandas).
    if (mine.length > 0) {
      const resp = await fetch(
        `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
        {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
            "Accept": "application/vnd.github+json",
            "User-Agent": "whatsapp-news-webhook",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ event_type: "more-news" }),
        }
      );
      console.log(`repository_dispatch -> HTTP ${resp.status}`); // 204 = ok
    }

    // Siempre responder 200 rápido: si el webhook falla seguido, Meta lo
    // reintenta y termina desactivándolo.
    return new Response("ok", { status: 200 });
  },
};

async function validSignature(body, header, secret) {
  if (!header.startsWith("sha256=")) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
  const expected =
    "sha256=" +
    [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return expected === header;
}
