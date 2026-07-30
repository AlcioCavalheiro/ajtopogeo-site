/* AJ TopoGeo Campo — service worker (instalável + abre offline).
   NÃO cacheia chamadas ao Supabase (dados/fotos sempre na rede). */
const CACHE='campo-v2';
const SHELL=[
  '/campo/','/campo/index.html','/campo/manifest.webmanifest',
  '/campo/icon-180.png','/campo/icon-192.png','/campo/icon-512.png',
  'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2',
  'https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@2.47.0/tabler-icons.min.css'
];

self.addEventListener('install',e=>{
  e.waitUntil(caches.open(CACHE).then(c=>Promise.allSettled(SHELL.map(u=>c.add(u)))).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',e=>{
  e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',e=>{
  const req=e.request;
  if(req.method!=='GET')return;                              // writes do Supabase passam direto
  const url=new URL(req.url);
  if(url.hostname.includes('supabase.co'))return;            // API e Storage: sempre rede
  if(req.mode==='navigate'){                                 // navegação: rede, fallback no shell
    e.respondWith(fetch(req).catch(()=>caches.match('/campo/index.html')));
    return;
  }
  e.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(r=>{
    const cp=r.clone();caches.open(CACHE).then(c=>c.put(req,cp).catch(()=>{}));return r;
  }).catch(()=>hit)));
});
