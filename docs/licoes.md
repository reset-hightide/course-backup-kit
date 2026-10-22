# Lições do primeiro backup (Hubla, out/2026)

O que deu errado ou surpreendeu, e a decisão de projeto que saiu de cada coisa.

| Problema | O que fizemos |
|---|---|
| Baixar pelo Chrome (Flatpak/Wayland) abre a janela "Salvar como", que a automação não alcança. Extensões tipo "video downloader" também ficam fora de alcance. | Nada é baixado pelo Chrome: a página manda os bytes ou os links para um servidor em 127.0.0.1. |
| Página https falando com 127.0.0.1 é bloqueada pelo Chrome (Private Network Access). | Servidor responde `Access-Control-Allow-Private-Network: true` e CORS só para a origem do curso. O usuário clica "Permitir" uma vez. |
| A API exigia `Authorization: Bearer`, não cookie. | O adaptador lê o token do Firebase no IndexedDB da própria página a cada chamada (renova sozinho). |
| ffmpeg baixando HLS do Cloudflare Stream: ~0,3 MB/s (segmentos minúsculos, um por vez). 175 vídeos levariam ~19 h, e os links expiram em ~24 h. | `cbk/hls.py` baixa 12 segmentos em paralelo e junta com ffmpeg `-c copy`: ~7 MB/s. 2 vídeos por vez. |
| Vídeo e áudio em playlists separadas (fMP4). | Escolhe a variante de maior BANDWIDTH, acha o grupo de áudio dela e faz `-map 0:v -map 1:a`. |
| Destino num OneDrive montado com rclone: escrever direto é lento e deixa arquivo pela metade. | Monta o vídeo em `~/.cache` e só move no fim; anexos gravam em `.part` e trocam de nome. |
| O usuário já tinha pastas de aulas baixadas à mão, com outro padrão de nome. | `aliases`: título da aula → pasta existente; e o script pula pasta que já tem vídeo/anexo. |
| Avisos pelo WhatsApp Web falharam com duas abas do WhatsApp abertas (a do usuário e a do Claude). | Uma aba só, aberta pelo Claude. O watcher `--once` acorda o Claude, que manda a mensagem. |
| O log era texto solto, difícil de resumir no fim. | `events.jsonl` (um evento por linha) + `progress.log` legível + relatório automático no fim. |
