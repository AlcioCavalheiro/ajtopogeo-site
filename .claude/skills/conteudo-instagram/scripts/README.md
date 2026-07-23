# Scripts da rotina de conteúdo do Instagram

Tudo é dirigido por um único `pauta.json`. Os scripts não decidem nada de
conteúdo — quem escolhe texto, imagem e corte é a etapa de redação. Isso é de
propósito: refazer uma peça vira editar JSON, não reescrever código.

## Ambiente

Roda no venv da empresa, o mesmo da triagem de imóvel:

```powershell
& C:\Users\ALCIO\.ajtopogeo\venv\Scripts\python.exe -m pip install `
    pillow opencv-python-headless numpy reportlab imageio-ffmpeg pypdfium2
```

- `pillow` — desenha os cards e as capas.
- `opencv-python-headless` + `numpy` — extrai frames, monta contact sheet.
- `imageio-ffmpeg` — traz o binário do ffmpeg. Não há ffmpeg no PATH da
  máquina; é este pacote que fornece.
- `reportlab` — compõe o guia em PDF.
- `pypdfium2` — rasteriza o PDF para conferir as páginas olhando. Não há
  poppler instalado, então `pdftoppm` não funciona.

## Os seis scripts

| script | entrada | saída |
| --- | --- | --- |
| `preparar.py` | zip/pasta/arquivos `--saida <trabalho>` | `material.json` + contact sheets em `sheets/` |
| `recortar.py` | `recortes.json` | `SEGURA_*.jpg` em 1080×1350 ou 1080×1920 |
| `render.py` | `pauta.json` | cards dos carrosséis e capas de Reel |
| `montar_reel.py` | `pauta.json` | `<id>_REEL.mp4` + `<id>_cenas.jpg` |
| `guia_pdf.py` | `pauta.json` | `GUIA_PUBLICACAO_<data>.pdf` |
| `registrar.py` | `pauta.json` | acrescenta a sessão à pauta do mês no Drive |

Bibliotecas: `marca.py` (paleta, tipografia, foto de fundo, rodapé) e
`diagramas.py` (os diagramas esquemáticos dos cards).

## Padrão visual

Cores do `css/style.css` do site. Mexer aqui muda a cara de tudo — confira
contra o site antes.

| elemento | cor |
| --- | --- |
| fundo | `#0d1b2a` |
| bloco secundário | `#112233` · `#1a3a5c` |
| destaque, tarja, rótulo | `#3E8FC4` |
| texto | `#f0f4f8` |
| texto secundário | `#8899aa` |
| cota / marcação do diagrama | `#e2a85c` |
| água | `#60b2e8` |

Tipografia: Segoe UI de `C:\Windows\Fonts` substituindo a Inter do site —
`seguibl` nos títulos, `seguisb` no corpo, `segoeuib` nos rótulos. A logo de
`gestor/LOGO.png` **não serve**: é texto preto sobre fundo branco e desaparece
no azul-marinho. A assinatura dos cards é tipográfica.

Formatos: carrossel 1080×1350, Reel e story 1080×1920, margem de 90 px.

## O pauta.json

```jsonc
{
  "data": "2026-07-22",              // AAAA-MM-DD, define o nome do PDF e do mês
  "data_br": "22/07/2026",           // cabeçalho do PDF
  "servico": "...",                  // uma linha, vai para a pauta do mês
  "subtitulo": "...",                // rótulo da capa do PDF
  "resumo": "...",                   // parágrafo de abertura do PDF
  "contexto": "...",                 // contexto técnico, só na pauta do mês
  "pasta_saida": "C:/.../POST_...",  // barras normais; evita dor de escape
  "pasta_trabalho": "C:/...",        // PNGs de legenda do Reel
  "pasta_pauta": "G:/...",           // opcional; padrão é a pasta do Drive

  "antes_de_subir": [{ "item": "...", "detalhe": "..." }],
  "fora":        [{ "material": "...", "motivo": "..." }],
  "liberado":    "o que foi conferido e está liberado",
  "pendencias":  [{ "item": "...", "situacao": "..." }],
  "onde":        [{ "pasta": "...", "conteudo": "..." }],

  "pecas": [
    {
      "id": "P1", "formato": "carrossel", "eixo": "curiosidade técnica",
      "titulo": "...", "quando": "quarta",
      "legenda": "primeira linha é o gancho\n\nparágrafos separados por \\n\\n",
      "hashtags": ["#topografia", "..."],
      "montagem": "observação que vai para o PDF",
      "cards": [
        { "tipo": "capa", "slug": "capa", "rotulo": "CURIOSIDADE TÉCNICA",
          "rotulo_curto": "capa", "titulo": "TÍTULO EM VERSAL",
          "sub": "linha de apoio", "bg": "caminho/da/imagem.jpg" },
        { "tipo": "corpo", "slug": "mds", "rotulo": "O QUE O DRONE ENTREGA",
          "rotulo_curto": "MDS", "texto": "90 a 220 caracteres",
          "bg": "outra/imagem.jpg", "selo": "NBR 13133 · ART/CFT",
          "diagrama": { "tipo": "perfil_mata", "mds": true } }
      ]
    },
    {
      "id": "P2", "formato": "reel", "eixo": "bastidor de campo",
      "titulo": "...", "quando": "sexta",
      "legenda": "...", "hashtags": ["..."],
      "passos": ["instrução 1", "instrução 2"],
      "capa": { "rotulo": "...", "titulo": "...", "sub": "...",
                "bg": "...", "zoom": 1.42, "anchor_y": 0.10 },
      "cenas": [
        { "fonte": "C:/.../video.mp4", "ini": 26.0, "fim": 30.0,
          "vel": 1.0, "texto": "VISTORIA DE LOCAL", "estilo": "label" }
      ]
    }
  ]
}
```

Estilos de legenda do Reel: `label` (rótulo em versal), `linha` (frase),
`destaque` (frase grande), `assinatura` (fecho da marca). Texto vazio =
cena sem legenda.

## Diagramas

`perfil_mata` — mata em corte. Explica MDS × MDT, altura de dossel, ponto
levantado no chão.
`mds`, `mdt` (bool) · `cota` (texto da medida, ex. `"+15 m"`) ·
`pontos` (bool) · `top` (padrão 780).

`perfil_vertente` — ocupação no platô, mata na encosta, fundo de vale. Serve
para drenagem, terraplenagem, talvegue, APP.
`topo_rotulo` · `agua` (bool) · `curvas` (bool) · `lancamento` (bool) ·
`marcas`: lista de `[posicao_0a1, "TEXTO", "solo|meio|copa"]`.

Diagrama novo: escreva a função, registre em `DIAGRAMAS` e documente aqui.
Quem lê os cards é topógrafo e engenheiro — diagrama errado custa mais caro
que diagrama ausente.

## Armadilhas já pagas

**Imagem de fundo repetida.** `render.py` sai com código 2 se duas peças usarem
a mesma imagem. Foi decisão consciente: cards com a mesma foto lêem como
preguiça. Se faltar material, extraia frames de outros trechos do vídeo.

**Marcador do diagrama na cota errada.** Sub-bosque tem que apontar para dentro
da mata, talvegue para o fundo do vale. Apontar tudo para o topo da copa está
tecnicamente errado e o público percebe.

**Rótulo estourando a margem.** `_rot()` em `diagramas.py` limita o x ao
intervalo do desenho. Rótulo novo tem que passar por lá.

**Texto sumindo no céu claro.** O degradê do topo em `foto_fundo` é linear de
propósito. Com curva, a faixa do meio clareia e o corpo perde contraste.

**Capa de Reel cortada na grade.** O Instagram usa um recorte 1:1 centrado
(y 420–1500 de 1920) na grade do perfil, e a interface do player come os
últimos ~400 px. Todo texto da capa fica nessa faixa.

**Assunto atrás do título.** Quando a foto é 9:16 exata não sobra recorte, e o
assunto cai justo onde o título entra. Use `zoom` com `anchor_y` baixo para
empurrar o assunto para baixo.

**Áudio de campo estourando.** Vento no microfone leva o pico a −0,6 dB. O
`montar_reel.py` aplica passa-alta de 90 Hz e limitador, o que traz para cerca
de −2,7 dB sem descaracterizar o ambiente. Nunca troque por música.

**Vídeo de WhatsApp.** Vem em 478×850. Ampliar para 1080×1920 resolve para o
feed mas não recupera detalhe — registre a pendência de pedir o original do
celular. O vídeo que sai do cartão do drone vem em 4K e não tem esse problema.

**Escape de caminho no JSON.** Use barras normais (`C:/Users/...`). O Windows
aceita, e evita a classe inteira de erro de `\U` inválido.

**Tabela do PDF estourando a página.** Toda célula tem que virar `Paragraph`
para quebrar linha — string crua não quebra. Já tratado em `tabela()`.

**Negrito no PDF.** `<b>` só funciona depois de `registerFontFamily`. Já
registrado.
