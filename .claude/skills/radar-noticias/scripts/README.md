# Scripts da rotina Radar de Notícias

A rotina transforma uma notícia do setor em três entregas: um **post de blog**,
um **carrossel** e um **Reel narrado** para o Instagram. Cada entrega é dirigida
por um JSON — o script não decide conteúdo, só monta. Mesma filosofia da rotina
de conteúdo de campo.

## Ambiente

O mesmo venv da empresa, o das outras rotinas de conteúdo:

```
C:\Users\ALCIO\.ajtopogeo\venv\Scripts\python.exe
```

Pacotes já instalados nele: `pillow`, `opencv-python-headless`, `numpy`,
`imageio-ffmpeg`, `reportlab`, `pypdfium2` e **`edge-tts`** (locução neural).
Não há ffmpeg nem ffprobe no PATH da máquina — o binário do ffmpeg vem do
`imageio-ffmpeg`, e a duração do áudio é lida do próprio ffmpeg.

## Os scripts e de onde vêm

| script | onde fica | entrada | saída |
| --- | --- | --- | --- |
| `gerar_post_blog.py` | `rotinas/` | `post.json` | `blog-<slug>.html` + card em `blog.html` + entrada no `sitemap.xml` |
| `render.py` | `.claude/skills/conteudo-instagram/scripts/` | `pauta.json` | cards do carrossel + capa do Reel |
| `reel_noticia.py` | **aqui** | `pauta.json` | `<id>_REEL.mp4` + `<id>_CAPA_REEL.jpg` + `<id>_cenas.jpg` |
| `guia_pdf.py` | `.claude/skills/conteudo-instagram/scripts/` | `pauta.json` | `GUIA_PUBLICACAO_<data>.pdf` |

`reel_noticia.py` importa `marca.py` (paleta e tipografia) dos scripts da rotina
de conteúdo, resolvendo o caminho sozinho — não precisa copiar a marca. Rode
`render.py` e `guia_pdf.py` a partir da pasta deles; rode `reel_noticia.py` a
partir daqui. O `pauta.json` é o mesmo arquivo para os três (use caminho
absoluto).

## Por que um Reel novo, e não o `montar_reel.py`

O `montar_reel.py` da rotina de campo corta **vídeo** com **som ambiente** — é
o contrato dele, e não se mexe nele. Notícia não tem filmagem de campo nova.
`reel_noticia.py` monta um **slideshow narrado** sobre fotos do acervo (`img/`),
com locução neural (edge-tts) e sem música. É o formato certo para notícia.

## O `post.json` (blog)

Esquema completo e comentado em `rotinas/exemplo-post-blog.json`. Campos
narrativos (`hero_h1`, `hero_lead`, `intro`, `paragrafos`, `lista`) aceitam HTML
inline; campos de atributo são escapados. O `slug` vira `blog-<slug>.html` e a
URL limpa `/blog-<slug>`. O script recusa slug repetido, imagem inexistente e
categoria fora de `geo/topo/reg/amb/drone/doc`.

## O `pauta.json` (Instagram)

Reaproveita o esquema do `pauta.json` da rotina de conteúdo (ver
`../../conteudo-instagram/scripts/README.md`), com uma diferença: a peça de Reel
usa a chave **`narracao`** em vez de `cenas`.

```jsonc
{
  "data": "2026-07-29", "data_br": "29/07/2026",
  "servico": "Notícia: INCRA unifica sistemas de dados de terras",
  "subtitulo": "RADAR DE NOTÍCIAS", "resumo": "...",
  "pasta_saida": "C:/Users/ALCIO/Pictures/POST_NOTICIA_.../",
  "pasta_trabalho": "C:/.../scratchpad",
  "voz": "pt-BR-AntonioNeural",   // opcional; padrão AntonioNeural
  "rate": "+0%",                  // opcional; ritmo da locução

  "pecas": [
    {
      "id": "C1", "formato": "carrossel", "eixo": "notícia", "quando": "post 1",
      "titulo": "...", "legenda": "gancho na 1a linha\\n\\n...",
      "hashtags": ["#georreferenciamento", "..."],
      "cards": [ { "tipo": "capa", ... }, { "tipo": "corpo", ... } ]
    },
    {
      "id": "R1", "formato": "reel", "eixo": "notícia", "quando": "post 2",
      "titulo": "...", "legenda": "...", "hashtags": ["..."],
      "passos": ["...", "..."],
      "narracao": [
        { "tipo": "capa", "imagem": "img/marco-geodesico.jpg",
          "rotulo": "NOVIDADE", "titulo": "...", "sub": "...",
          "narracao": "texto falado (para o OUVIDO)" },
        { "tipo": "slide", "imagem": "img/campo-gnss.jpg", "estilo": "linha",
          "rotulo": "O ponto principal", "texto": "TEXTO NA TELA (para o OLHO)",
          "narracao": "texto falado deste slide" }
      ]
    }
  ]
}
```

Regras do Reel narrado:

- **`narracao` é para o ouvido, `texto` é para o olho.** Escreva os dois
  separados: "m²", "nº", siglas e números ficam bons de ler e ruins de ouvir.
- **Sem música** — a trilha é só a locução. Não troque por música de acervo.
- Cada slide dura pelo menos a locução + folga, sempre acima do piso de leitura,
  então a legenda fica tempo suficiente na tela.
- Todo texto fica na faixa **420–1500** do quadro (recorte 1:1 da grade do
  perfil + UI do player). Fora dela o texto some.
- O primeiro slide (capa) também sai como `<id>_CAPA_REEL.jpg`, para subir como
  capa do Reel no Instagram.
- `estilo` do slide de corpo: `linha` (frase), `destaque` (frase grande),
  `label` (rótulo em versal).

## Armadilhas já pagas

**`zoompan` do ffmpeg é uma armadilha aqui.** Com `-loop 1` ele explode o número
de quadros (arquivo gigante, minutos de processamento). O movimento Ken Burns
vem de um `crop` animado sobre um `scale` único — custo quase nulo. Não troque
por zoompan.

**Imagem de fundo repetida.** Assim como no `render.py`, cada card/slide deve ter
a sua foto. Reaproveitar a mesma foto lê como preguiça. O acervo em `img/` tem
19 fotos — dá e sobra.

**Narração literal.** O edge-tts lê o texto como está. Revise `narracao` lendo
em voz alta antes de gerar; abreviação lida errado só aparece no áudio final.
