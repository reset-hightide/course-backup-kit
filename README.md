# course-backup-kit

[![testes](https://github.com/reset-hightide/course-backup-kit/actions/workflows/testes.yml/badge.svg)](https://github.com/reset-hightide/course-backup-kit/actions/workflows/testes.yml)

Backup **organizado** de cursos online que você comprou: vídeos e anexos de cada aula, salvos na
mesma estrutura de módulos e aulas do site, com catálogo, log, relatório e avisos de progresso
(WhatsApp, Telegram, ntfy, notificação do sistema...).

Nasceu do backup de um curso na Hubla: 190 vídeos + 316 anexos, 24 GB, 0 erros, rodando sozinho
por horas e mandando uma mensagem no WhatsApp a cada módulo concluído.

```
Curso/
├── _Catálogo do curso.csv          módulo, aula, pasta, duração, anexos
├── _Relatório do backup.md         totais, tempo de aula, erros
├── Módulo 1: Introdução/
│   ├── 1 Boas-vindas/
│   │   ├── video.mp4
│   │   ├── Slides.pdf
│   │   └── Planilha.xlsx
│   └── 2 Leia antes de começar/
│       └── Descrição.txt           aulas só de texto
└── Módulo 2: Prática/ ...
```

> **Uso pessoal.** Serve para guardar uma cópia do conteúdo ao qual você tem acesso legítimo. Respeite os termos da
> plataforma e os direitos dos autores: não redistribua o conteúdo.

## Como funciona

```
 Chrome (aba logada no curso)                      sua máquina
┌───────────────────────────────┐   PUT anexos   ┌──────────────────────┐   ┌──────────────┐
│ client/core.js                │ ─────────────► │ cbk.py serve         │──►│ pasta do     │
│  + adapters/<site>.js         │  POST /video   │  fila de vídeos      │   │ curso        │
│   (lista módulos/aulas pela   │ ─────────────► │  HLS paralelo+ffmpeg │   │ (local ou    │
│    API do próprio site)       │  POST /event   │  events.jsonl + log  │   │  nuvem)      │
└───────────────────────────────┘                └──────────┬───────────┘   └──────────────┘
                                                            │
                                          cbk.py watch ◄────┘  avisos: WhatsApp, Telegram, ntfy...
```

- **A página faz o que só ela pode fazer**: está logada, então lê a API do site e baixa os anexos com
  os cookies/tokens dela. Sem senha no script.
- **O servidor local faz o trabalho pesado**: grava arquivos, baixa vídeos HLS com 12 segmentos em
  paralelo (~20x mais rápido que o ffmpeg sozinho) e junta vídeo + áudio com ffmpeg, sem reencodar.
- **O adaptador é a única parte específica de cada site**: duas funções, `listModules()` e `getLesson()`.
- **Idempotente**: rodar de novo pula o que já existe. O dry run mostra o plano antes de baixar.

## Uso rápido

Funciona em **Windows, macOS e Linux** (testado nos três a cada envio, veja o selo acima).
Requisitos: Python 3.10+ (só biblioteca padrão), `ffmpeg`/`ffprobe` e Chrome (ou outro navegador Chromium, como Edge).

| | Windows (PowerShell) | macOS | Linux |
|---|---|---|---|
| Python | `winget install Python.Python.3.13` | `brew install python` | já vem instalado |
| ffmpeg | `winget install Gyan.FFmpeg` | `brew install ffmpeg` | `sudo apt install ffmpeg` |
| comando | `python` (ou `py`) | `python3` | `python3` |

```bash
git clone https://github.com/reset-hightide/course-backup-kit
cd course-backup-kit
python3 cbk.py doctor                                  # confere Python, ffmpeg e pastas
```

Copie `config.example.json` para `configs/meu-curso.json` e edite `name`, `adapter`, `origin` e `dest`.
No Windows, use barras normais ou duplas no `dest`: `"C:/Users/voce/Cursos/X"`.

```bash
python3 cbk.py serve -c configs/meu-curso.json
```

Na aba do curso, abra o DevTools (F12) > Console e cole:

```js
const s = document.createElement('script'); s.src = 'http://127.0.0.1:8765/client.js'; document.head.append(s);
await new Promise(r => s.onload = r);
await CourseBackup.run('hubla', {dry: true});   // plano em "_Plano do backup.csv", nada é baixado
await CourseBackup.run('hubla', {dry: false});  // backup de verdade
```

Se o site bloquear o script externo (CSP), use `python3 cbk.py js -c configs/meu-curso.json` e cole a saída.
Na primeira vez o Chrome pergunta se o site pode acessar a rede local: clique em **Permitir**.

Acompanhe e receba avisos:

```bash
python3 cbk.py watch -c configs/meu-curso.json     # avisa por módulo, em erro e no fim
```

O `cbk.py doctor -c configs/meu-curso.json` mostra onde fica o log (`progress.log`) neste computador:

| sistema | logs e estado | cache dos vídeos sendo montados |
|---|---|---|
| Windows | `%LOCALAPPDATA%\course-backup-kit\data` | `%LOCALAPPDATA%\course-backup-kit\cache` |
| macOS | `~/Library/Application Support/course-backup-kit` | `~/Library/Caches/course-backup-kit` |
| Linux | `~/.local/share/course-backup-kit` | `~/.cache/course-backup-kit` |

### Nomes de pasta no Windows

O Windows não aceita `: * ? " < > |` em nomes de arquivo, e limita o caminho a 260 caracteres. Com
`"safe_names": "auto"` (padrão), no Windows `Módulo 1: Introdução` vira `Módulo 1 - Introdução` e nomes
muito longos são encurtados. Use `"windows"` para ter os mesmos nomes em todos os sistemas (bom se a pasta
for sincronizada com OneDrive ou Google Drive), ou `"none"` para manter os nomes exatos do site.

## Com o Claude Code (recomendado)

O repositório traz uma skill, `.claude/skills/course-backup/SKILL.md`, com o passo a passo para o
Claude Code com a extensão [Claude in Chrome](https://claude.com/chrome). Abra o Claude Code na pasta do
projeto e peça, por exemplo:

> faz backup do curso https://... na pasta ~/Cursos/X e me avisa no grupo "Lembrete" do WhatsApp a cada módulo

Ele descobre a API do site (e escreve o adaptador, se não existir), faz o dry run, mostra o plano, roda e
manda os avisos pelo WhatsApp Web usando `cbk.py watch --once`.

## Avisos (`notify` no config)

| tipo | exemplo |
|---|---|
| `stdout` | `{"type": "stdout"}` |
| `desktop` | `{"type": "desktop"}` notificação do sistema no Windows, macOS ou Linux |
| `command` | `{"type": "command", "cmd": ["notify-send", "Backup"]}` (mensagem vai como último argumento) |
| `ntfy` | `{"type": "ntfy", "topic": "um-topico-dificil-de-adivinhar"}` → app ntfy no celular |
| `telegram` | `{"type": "telegram", "token": "<bot token>", "chat_id": "<id>"}` |
| `webhook` | `{"type": "webhook", "url": "https://...", "field": "text"}` (Slack, Discord, n8n...) |
| `callmebot` | `{"type": "callmebot", "phone": "+55...", "apikey": "..."}` WhatsApp via [CallMeBot](https://www.callmebot.com/) |

WhatsApp Web pelo Claude in Chrome não precisa de config: veja a skill.

## Criar um adaptador

Copie `adapters/_template.js` (há instruções de como achar a API no DevTools) e veja `adapters/demo.js`
(mínimo) e `adapters/hubla.js` (real). Contrato:

```js
CourseBackup.register({
  name: 'meusite',
  async listModules() { return [{title, lessons: [{id, title}]}]; },
  async getLesson(lesson, module) {
    return {title, video: {url, kind: 'hls' | 'file', durationSec}, attachments: [{name, url}], text};
  },
});
```

Opções de nome no config (`client`): `moduleFolder`, `lessonFolder` (`{n}`, `{nn}`, `{title}`), `videoName`.
`aliases` aponta para um JSON `{"título da aula em minúsculas": "pasta/existente"}` para reaproveitar pastas antigas.

## Adaptadores

| site | status |
|---|---|
| Hubla (`app.hub.la`) | testado em 2026-10 |
| demo (`tests/fake_site.py`) | curso falso, para testes |

## Testes

```bash
python3 tests/e2e.py                 # servidor + HLS + watcher + relatório, sem navegador (roda no CI nos 3 sistemas)
python3 tests/fake_site.py           # curso falso em :8899 para testar o client/core.js no Chrome (adapter "demo")
```

## Estrutura

```
cbk.py              CLI: serve | js | watch | report | video | doctor
cbk/server.py       servidor local (PUT arquivo, POST /video, /event, /ls, /status, /client.js)
cbk/hls.py          download HLS paralelo / arquivo direto + ffprobe
cbk/watch.py        avisos por módulo/erro/fim + relatório
cbk/notify.py       destinos dos avisos
cbk/paths.py        diferenças entre sistemas: pastas do app e nomes válidos no Windows
client/core.js      roda na página: pastas, pular existentes, catálogo, progresso
adapters/*.js       um por site
docs/licoes.md      o que deu errado no caminho e por que o kit é assim
```

## Licença

MIT
