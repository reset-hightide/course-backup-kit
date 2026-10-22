// Adaptador do curso falso de tests/fake_site.py (http://127.0.0.1:8899). Serve de exemplo mínimo.
CourseBackup.register({
  name: 'demo',
  async listModules() {
    return (await fetch('/api/modules')).json();
  },
  async getLesson(l) {
    const d = await (await fetch('/api/lessons/' + l.id)).json();
    return {
      title: d.title,
      video: d.video ? {url: d.video, kind: 'hls', durationSec: d.duration} : null,
      attachments: d.files,
      text: d.html ? CourseBackup.util.htmlToText(d.html) : '',
    };
  },
});
