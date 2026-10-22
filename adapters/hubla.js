// Adaptador: Hubla (app.hub.la), área de membros. Testado em 2026-10 (190 vídeos + 316 anexos).
// Abra a página do curso (app.hub.la/m/<produto>) logado, espere a lista de módulos carregar e rode.
// - Token: Firebase Auth guardado no IndexedDB da própria página (renova sozinho enquanto a aba está aberta).
// - Lista: a página já chamou hub/sections/v2; reaproveitamos a mesma URL (achada no performance log).
// - Vídeo: cover.url é um manifest HLS do Cloudflare Stream; o token do link expira em ~24h.
// - Anexos: URLs assinadas, baixadas pela própria página (cookies/CORS dela) e enviadas por PUT.
CourseBackup.register((() => {
  const API = 'https://backend-bff-members-area.platform.hub.la/api/v1/';
  const token = async () => {
    const db = await new Promise((res, rej) => { const r = indexedDB.open('firebaseLocalStorageDb'); r.onsuccess = () => res(r.result); r.onerror = rej; });
    const all = await new Promise(res => { const t = db.transaction('firebaseLocalStorage').objectStore('firebaseLocalStorage').getAll(); t.onsuccess = () => res(t.result); });
    const u = all.find(x => x.value && x.value.stsTokenManager);
    if (!u) throw new Error('não achei o login do Firebase: você está logado na Hubla nesta aba?');
    return u.value.stsTokenManager.accessToken;
  };
  const api = url => CourseBackup.util.retry(async () => {
    const r = await fetch(url.startsWith('http') ? url : API + url, {headers: {Authorization: 'Bearer ' + await token()}});
    if (!r.ok) throw new Error('API ' + r.status + ' ' + url);
    return r.json();
  });

  return {
    name: 'hubla',
    async listModules() {
      const url = performance.getEntriesByType('resource').map(e => e.name).find(n => /hub\/sections\/v2/.test(n));
      if (!url) throw new Error('abra a página do curso (lista de módulos) antes de rodar');
      const j = await api(url);
      const items = [...(j.items || j)].sort((a, b) => a.order - b.order);
      return items.map(s => ({
        title: s.name,
        lessons: [...s.posts].sort((a, b) => a.order - b.order).map(p => ({id: p.id, title: p.title})),
      }));
    },
    async getLesson(l) {
      const d = await api('hub/posts/' + l.id);
      const v = d.cover && d.cover.type === 'video' && d.cover.url;
      return {
        title: d.title,
        video: v ? {url: d.cover.url, kind: 'hls', durationSec: (d.cover.metadata || {}).duration} : null,
        attachments: (d.attachments || []).filter(a => a.url).map(a => ({name: a.name, url: a.url})),
        text: d.body ? CourseBackup.util.htmlToText(d.body) : '',
      };
    },
  };
})());
