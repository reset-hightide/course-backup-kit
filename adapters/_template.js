// Modelo de adaptador. Copie para adapters/<site>.js, troque "meusite" e preencha as duas funções.
// Um adaptador só responde "o que existe no curso"; pastas, pular o que já foi baixado, catálogo,
// envio ao servidor e progresso ficam no client/core.js.
//
// Como descobrir a API de um site (DevTools > Network, ou peça ao Claude Code com Claude in Chrome):
//  1. Abra a página do curso e filtre por Fetch/XHR: procure o JSON com a lista de módulos/aulas.
//  2. Abra uma aula: procure o JSON da aula (título, vídeo, anexos) e o .m3u8 / .mp4 do vídeo.
//  3. Veja como a página se autentica (cookie, header Authorization, token no localStorage/IndexedDB).
//  4. Se o vídeo só aparece no player: performance.getEntriesByType('resource') lista as URLs carregadas.
CourseBackup.register({
  name: 'meusite',

  // -> [{title: 'Módulo 1', lessons: [{id, title}, ...]}, ...] na ordem do curso
  async listModules() {
    const r = await fetch('/api/course/123/modules', {credentials: 'include'});
    const j = await r.json();
    return j.modules.map(m => ({title: m.name, lessons: m.lessons.map(l => ({id: l.id, title: l.name}))}));
  },

  // -> detalhes de uma aula. Tudo é opcional, menos o título.
  async getLesson(lesson, module) {
    const d = await (await fetch('/api/lessons/' + lesson.id, {credentials: 'include'})).json();
    return {
      title: d.name,
      // kind: 'hls' (manifest .m3u8) ou 'file' (.mp4 direto). headers: extras para o download no servidor.
      video: d.video_url ? {url: d.video_url, kind: 'hls', durationSec: d.duration} : null,
      // url: baixada pela própria página (com os cookies dela). Ou {name, blob: async () => Blob}.
      attachments: (d.files || []).map(f => ({name: f.filename, url: f.download_url})),
      // texto da aula, salvo como Descrição.txt quando a aula não tem vídeo nem anexos
      text: d.html ? CourseBackup.util.htmlToText(d.html) : '',
    };
  },
});
