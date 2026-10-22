// course-backup-kit: núcleo que roda dentro da página do curso (aba já logada).
// O adaptador do site diz QUAIS são os módulos/aulas/vídeos/anexos; este núcleo cuida do resto:
// nomes de pasta, pular o que já existe, enviar ao servidor local, catálogo CSV e progresso.
// Progresso: JSON.stringify(CourseBackup.status)
(() => {
  const CB = window.CourseBackup = window.CourseBackup || {adapters: {}};
  CB.opts = {
    server: 'http://127.0.0.1:8765',
    moduleFolder: '{title}',          // placeholders: {n} {nn} {title}
    lessonFolder: '{n} {title}',
    videoName: 'video.mp4',
    catalog: '_Catálogo do curso.csv',
    plan: '_Plano do backup.csv',
  };
  CB.configure = o => Object.assign(CB.opts, o);
  CB.register = a => { CB.adapters[a.name] = a; return a; };

  const clean = s => String(s).replace(/[\/\\]/g, '-').replace(/[\u0000-\u001f]/g, '')
    .replace(/\s+/g, ' ').trim().replace(/[. ]+$/, '') || 'sem título';
  const norm = s => clean(s).toLowerCase();
  const fill = (tpl, n, title) => tpl.replace('{nn}', String(n).padStart(2, '0')).replace('{n}', n).replace('{title}', clean(title));
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  CB.util = {clean, sleep,
    retry: async (fn, tries = 4) => { for (let i = 0; ; i++) { try { return await fn(); } catch (e) { if (i >= tries - 1) throw e; await sleep(2000 * (i + 1)); } } },
    htmlToText: html => { const d = document.createElement('div'); d.innerHTML = html; return d.innerText; },
  };

  const S = () => CB.opts.server;
  const encPath = p => p.split('/').map(encodeURIComponent).join('/');
  const ls = async p => (await fetch(S() + '/ls?p=' + encodeURIComponent(p))).json();
  const exists = async p => (await (await fetch(S() + '/exists?p=' + encodeURIComponent(p))).json()).exists;
  const event = (type, data = {}) => fetch(S() + '/event', {method: 'POST', body: JSON.stringify({type, ...data})}).catch(() => {});
  const put = async (p, blob, group) => {
    const r = await fetch(S() + '/' + encPath(p), {method: 'PUT', body: blob, headers: group ? {'X-Group': encodeURIComponent(group)} : {}});
    if (!r.ok) throw new Error('PUT ' + r.status + ' ' + p);
  };
  const blobOf = async a => {
    if (a.blob) return a.blob();
    const r = await fetch(a.url, a.fetchOptions || {});
    if (!r.ok) throw new Error('anexo ' + r.status + ' ' + a.name);
    return r.blob();
  };
  CB.event = event;

  CB.run = async (name, {dry = true} = {}) => {
    const ad = CB.adapters[name];
    if (!ad) throw new Error('adaptador não registrado: ' + name);
    const st = CB.status = {adapter: name, dry, status: 'listando', done: 0, total: 0, videos: 0, files: 0,
                            skipVideos: 0, skipFiles: 0, errors: []};
    try {
      await (await fetch(S() + '/ping')).json();
    } catch (e) {
      st.status = 'servidor local inacessível: ' + e.message + ' (cbk.py serve rodando? o Chrome pediu permissão de rede local?)';
      return st;
    }
    const aliases = await (await fetch(S() + '/aliases')).json();
    try {
      const modules = await ad.listModules();
      st.total = modules.reduce((a, m) => a + m.lessons.length, 0);
      st.status = 'rodando';
      await event('run_start', {dry, adapter: name, modules: modules.length, lessons: st.total, url: location.href});
      const rows = [['Módulo', 'N', 'Aula', 'Pasta', 'Vídeo (min)', 'Anexos', 'Ação vídeo', 'Ação anexos']];
      for (const [mi, m] of modules.entries()) {
        const mod = fill(CB.opts.moduleFolder, mi + 1, m.title);
        for (const [li, l] of m.lessons.entries()) {
          const n = li + 1;
          try {
            const d = await ad.getLesson(l, m);
            const title = d.title || l.title;
            const folder = aliases[norm(title)] || mod + '/' + fill(CB.opts.lessonFolder, n, title);
            const have = await ls(folder);
            const atts = (d.attachments || []).filter(a => a.url || a.blob);
            let av = '-', aa = '-';
            if (d.video) {
              if (have.some(f => /\.(mp4|mkv|webm)$/i.test(f))) { av = 'já existe'; st.skipVideos++; }
              else {
                av = 'baixar'; st.videos++;
                if (!dry) await fetch(S() + '/video', {method: 'POST', body: JSON.stringify({
                  url: d.video.url, kind: d.video.kind || 'hls', headers: d.video.headers || {},
                  dest: folder + '/' + (d.video.name || CB.opts.videoName), group: m.title})});
              }
            }
            for (const a of atts) {
              const nm = clean(a.name);
              if (have.length && await exists(folder + '/' + nm)) { st.skipFiles++; aa = aa === '-' ? 'já existe' : aa; continue; }
              aa = 'baixar'; st.files++;
              if (!dry) await put(folder + '/' + nm, await CB.util.retry(() => blobOf(a)), m.title);
            }
            if (!d.video && !atts.length && d.text && !have.length) {
              aa = 'texto';
              if (!dry) await put(folder + '/Descrição.txt', new Blob([title + '\n\n' + d.text]), m.title);
            }
            rows.push([m.title, n, title, folder, d.video && d.video.durationSec ? Math.round(d.video.durationSec / 60) : '',
                       atts.map(a => a.name).join(' | '), av, aa]);
          } catch (e) {
            st.errors.push(m.title + ' #' + n + ': ' + e.message);
            rows.push([m.title, n, l.title, '', '', '', 'ERRO', e.message]);
            await event('lesson_error', {group: m.title, lesson: m.title + ' / ' + n + ' ' + l.title, error: e.message, dry});
          }
          st.done++;
        }
      }
      const csv = '﻿' + rows.map(r => r.map(c => '"' + String(c).replace(/"/g, '""') + '"').join(';')).join('\r\n');
      await put(dry ? CB.opts.plan : CB.opts.catalog, new Blob([csv]));
      await event('run_end', {dry, lessons: st.total, videos: st.videos, files: st.files,
                              skip_videos: st.skipVideos, skip_files: st.skipFiles, errors: st.errors.length});
      st.status = 'terminado';
    } catch (e) {
      st.status = 'fatal: ' + e.message;
      await event('run_fatal', {error: e.message, dry});
    }
    return st;
  };
})();
