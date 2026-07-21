# Pedir más noticias escribiendo por WhatsApp

Con esto configurado, le escribes **"más"** (o cualquier texto) a un número de
WhatsApp y en ~2 minutos te llegan 3 noticias extra al chat de CallMeBot.

Cómo fluye: tu mensaje → número del bot (Meta) → webhook (`worker.js` en
Cloudflare) → dispara el workflow **Más noticias** en GitHub → el script envía
las noticias por CallMeBot, igual que el digest diario.

Importante para calibrar expectativas:

- **Escribes en un chat y la respuesta llega en otro.** Le escribes al número
  de prueba de Meta, y las noticias llegan por el chat de CallMeBot de siempre.
  (Responder en el mismo chat es posible como mejora futura: requiere un token
  permanente de Meta y un sender nuevo; de paso permitiría jubilar a CallMeBot.)
- CallMeBot **no puede** leer mensajes — por eso se necesita el número de Meta
  como "oreja". Todo lo de esta guía es gratis y con APIs oficiales.
- Cada mensaje tuyo = una tanda de 3 noticias nuevas (sin repetir las
  anteriores). Tres "más" seguidos = 9 noticias.

## Paso 1 — App de WhatsApp en Meta (~10 min)

1. Entra a [developers.facebook.com](https://developers.facebook.com) con tu
   cuenta de Facebook/Instagram y crea una cuenta de desarrollador si no tienes.
2. **My Apps → Create App** → tipo **Business** (o "Other → Business").
3. Dentro de la app: **Add product → WhatsApp → Set up**.
4. En **WhatsApp → API Setup** vas a ver:
   - Un **número de prueba** (test number) — este es el número del bot.
     Agrégalo a tus contactos (ej: "Bot noticias").
   - El campo **To**: agrega ahí tu número personal como destinatario de
     prueba (te llega un código por WhatsApp para confirmarlo).
5. Anota el **App Secret**: está en **App Settings → Basic → App Secret**
   (botón *Show*). Se usa para que el webhook valide que los llamados vienen
   de Meta de verdad.

> El número de prueba permite hasta 5 destinatarios — para uso personal sobra.
> No necesitas token de acceso de Meta: este flujo solo **recibe** mensajes,
> y los tokens solo hacen falta para *enviar*.

## Paso 2 — Token de GitHub (~3 min)

1. GitHub → **Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token**.
2. Repository access: **Only select repositories** → `whatsapp_news`.
3. Permissions → Repository permissions → **Contents: Read and write**
   (es lo que exige el endpoint de `repository_dispatch`). Nada más.
4. Genera y copia el token (empieza con `github_pat_`).

## Paso 3 — Worker en Cloudflare (~5 min)

1. Crea cuenta gratis en [dash.cloudflare.com](https://dash.cloudflare.com).
2. **Workers & Pages → Create → Worker** (dale un nombre, ej `whatsapp-news`),
   deploy del hola-mundo, y luego **Edit code**: borra todo y pega el contenido
   de [`worker.js`](worker.js). Deploy.
3. En el worker: **Settings → Variables and Secrets**, agrega (como *Secret*):
   | Nombre         | Valor                                                  |
   |----------------|--------------------------------------------------------|
   | `VERIFY_TOKEN` | un string inventado por ti, ej: `pepino-atomico-77`    |
   | `APP_SECRET`   | el App Secret del paso 1.5                             |
   | `MY_PHONE`     | tu número sin `+`, ej: `56912345678`                   |
   | `GITHUB_REPO`  | `josesubiabre/whatsapp_news`                           |
   | `GITHUB_TOKEN` | el token del paso 2                                    |
4. Copia la URL pública del worker: `https://<nombre>.<cuenta>.workers.dev`.

## Paso 4 — Conectar el webhook en Meta (~2 min)

1. En la app de Meta: **WhatsApp → Configuration → Webhook → Edit**.
2. **Callback URL**: la URL del worker. **Verify token**: tu `VERIFY_TOKEN`.
3. **Verify and save** (si falla, revisa que el worker esté deployado y que el
   token coincida exactamente).
4. En **Webhook fields**, presiona **Manage** y suscríbete al campo
   **messages**.

## Paso 5 — Probar

Escríbele cualquier cosa al número de prueba desde tu WhatsApp. En el repo,
pestaña **Actions**, debería aparecer una ejecución de **Más noticias** en
segundos, y en ~1-2 minutos llegan las noticias al chat de CallMeBot.

Si no pasa nada:

- **Logs del worker**: en Cloudflare, pestaña *Logs* del worker (activa el
  stream y manda otro mensaje). `repository_dispatch -> HTTP 204` significa
  que GitHub recibió la orden; `401/404` es problema del `GITHUB_TOKEN` o
  `GITHUB_REPO`; si no aparece nada, el webhook de Meta no está llegando
  (revisa paso 4 y que tu número esté como destinatario de prueba).
- **En Actions no corre nada**: revisa que el workflow "Más noticias" exista
  en la rama `main` (el `repository_dispatch` solo mira la rama por defecto).

## Seguridad

- El worker **solo reacciona a mensajes de tu número** (`MY_PHONE`) y valida
  la **firma HMAC** de Meta con el `APP_SECRET` — otra persona que descubra la
  URL no puede gatillar envíos ni hacerse pasar por Meta.
- El `GITHUB_TOKEN` vive solo como secret del worker y únicamente puede tocar
  este repo.
