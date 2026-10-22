---
name: course-backup
description: Faz backup organizado de um curso online que o usuário comprou (vídeos + anexos, mesma estrutura de módulos/aulas), usando Claude in Chrome na aba logada, o servidor local do course-backup-kit e avisos de progresso (WhatsApp Web, ntfy, Telegram...). Use quando o usuário pedir para baixar/fazer backup/salvar offline um curso de uma plataforma web.
---

# Backup de curso com o course-backup-kit

Ideia: a **aba logada do navegador** lista o curso pela própria API do site e manda tudo para um
**servidor local** (`cbk.py serve`), que grava anexos e baixa os vídeos (HLS em paralelo + ffmpeg).
Um **watcher** acompanha o log e avisa a cada módulo concluído, problema ou fim.

Pré-requisitos: Python 3.10+, ffmpeg/ffprobe, Chrome com a extensão Claude in Chrome conectada.
Funciona em Windows, macOS e Linux. Comece com `python3 cbk.py doctor` (no Windows: `python cbk.py doctor`);
ele diz o que falta instalar e onde ficam os logs neste computador. Nos exemplos abaixo, troque
`python3` por `python` no Windows.

## 1. Combinar com o usuário
- Curso e plataforma (URL), e que ele **comprou/tem acesso** ao conteúdo (backup pessoal; não redistribuir).
- Pasta de destino (pode ser uma pasta sincronizada: OneDrive/Drive via rclone mount etc.).
- Como quer os avisos: WhatsApp Web (via você, passo 6), ntfy, Telegram, notify-send, só log.
- Se já existem pastas antigas de aulas que devem ser reaproveitadas (vira `aliases`).

## 2. Config
Copie `config.example.json` para `configs/<curso>.json` (a pasta `configs/` está no .gitignore) e preencha
`name`, `adapter`, `origin` (origem exata da página, ex. `https://app.hub.la`) e `dest`.
Rode `python3 cbk.py doctor -c configs/<curso>.json` para conferir pasta, porta e caminho do log.
Se a pasta for sincronizada (OneDrive, Google Drive) ou o usuário usa Windows, `"safe_names": "windows"`
troca `:` e outros caracteres proibidos (`Módulo 1: X` vira `Módulo 1 - X`).

## 3. Adaptador
Se existe `adapters/<plataforma>.js`, use. Senão, descubra a API (sempre na **sua** aba, nunca numa aba do usuário):
1. Abra o curso, depois uma aula. Com `javascript_tool`, liste as chamadas feitas:
   `performance.getEntriesByType('resource').map(e=>e.name).filter(n=>!/\.(js|css|png|jpg|svg|woff2?)/.test(n))`
2. Ache o JSON da lista de módulos e o JSON da aula (vídeo + anexos). Veja como autentica:
   cookie (`credentials:'include'`), ou token em localStorage/IndexedDB (ex.: Firebase `firebaseLocalStorageDb`).
3. Vídeo: procure `.m3u8` (HLS → `kind:'hls'`) ou `.mp4` direto (`kind:'file'`) no JSON da aula ou no performance log.
4. Copie `adapters/_template.js`, implemente `listModules()` e `getLesson()`. Mostre só formatos/chaves ao
   usuário, nunca tokens ou URLs assinadas inteiras.

## 4. Subir o servidor e testar
```bash
python3 cbk.py serve -c configs/<curso>.json      # em background
```
Na aba do curso, injete o script e faça um **dry run** (não baixa nada, grava `_Plano do backup.csv`):
```js
const s=document.createElement('script'); s.src='http://127.0.0.1:8765/client.js'; document.head.append(s);
await new Promise(r=>s.onload=r); JSON.stringify(await CourseBackup.run('<adaptador>',{dry:true}))
```
Se a CSP do site bloquear o `<script src>`, gere com `python3 cbk.py js -c ...` e execute o texto.
Na primeira vez o Chrome pede "acesso à rede local" para o site: **o usuário** precisa clicar em Permitir.
Mostre ao usuário o resumo do plano (aulas, vídeos, anexos, pastas) e só siga com o "ok" dele.

## 5. Rodar
```js
CourseBackup.run('<adaptador>',{dry:false}); 'started'          // progresso: JSON.stringify(CourseBackup.status)
```
Anexos vão na hora; vídeos entram numa fila no servidor (não dependem mais da aba).
Rodar de novo é seguro: pula o que já existe. Links de vídeo assinados expiram (Hubla/Cloudflare: ~24h):
se der erro 403 depois de muito tempo, rode o script de novo para enfileirar com links novos.

## 6. Acompanhar e avisar
- Avisos sem você: `python3 cbk.py watch -c configs/<curso>.json` em background (usa `notify` do config).
- Avisos pelo WhatsApp Web, por você: rode `python3 cbk.py watch -c ... --once` em background; quando ele
  terminar, leia o JSON (`message` já vem pronta), mande no chat combinado e relance o `--once`, até
  vir `"kind": "all_done"`.
  - Abra o WhatsApp Web numa aba **sua** e mantenha **uma** aba só: duas abas do WhatsApp no mesmo
    Chrome fazem a mensagem falhar ("não foi enviada").
  - Confirme com o usuário o nome do chat na primeira mensagem (envio de mensagem pede permissão).
- No fim: `_Relatório do backup.md` e `_Catálogo do curso.csv` ficam na pasta do curso; o log está em
  `progress.log` (humano) e `events.jsonl` (máquina), na pasta que o `doctor` mostra.

## Armadilhas conhecidas
- Chrome Flatpak/Wayland: downloads pelo navegador abrem "Salvar como" e travam a automação. Por isso tudo
  passa pelo servidor local em vez de downloads do Chrome.
- ffmpeg puro em HLS com segmentos pequenos é lento (~0,3 MB/s); o `cbk/hls.py` baixa 12 segmentos em paralelo.
- Pasta na nuvem (rclone mount, OneDrive): o vídeo é montado na pasta de cache do app e só movido no fim (`.part` + rename).
- Porta 8765 ocupada por outro programa: troque `port` no config (o `doctor` avisa).
