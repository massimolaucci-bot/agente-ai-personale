// Service worker minimo: serve solo a soddisfare i requisiti di installabilita'
// della PWA (Chrome/Android richiede un service worker registrato con un
// gestore "fetch"). Non fa caching e non intercetta le richieste in modo
// speciale: l'app resta sempre online e aggiornata dal server, semplicemente
// puo' essere installata come icona sulla schermata Home.
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  // Nessun intercetto: lascia passare tutte le richieste normalmente.
});
