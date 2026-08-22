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

## Os sete scripts

| script | entrada | saída |
| --- | --- | --- |
| `preparar.py` | zip/pasta/arquivos `--saida <trabalho>` | `material.json` + contact sheets em `sheets/` |
| `recortar.py` | `recortes.json` | `SEGURA_*.jpg` em 1080×1350 ou 1080×1920 |
| `render.py` | `pauta.json` | cards dos carrosséis e capas de Reel |
| `montar_reel.py` | `pauta.json` | `<id>_REEL.mp4` só com som ambiente |
| `montar_reel_narrado.py` | `pauta.json` | `<id>_REEL.mp4` com locução (é o padrão) |
| `guia_pdf.py` | `pauta.json` | `GUIA_PUBLICACAO_<data>.pdf` |
| `registrar.py` | `pauta.json` | acrescenta a sessão à pauta do mês no Drive |

Os dois montadores gravam o mesmo `<id>_REEL.mp4` e a mesma tira
`<id>_cenas.jpg` — rode **um** dos dois, não os dois.

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

## Reel narrado — o padrão

O usuário pediu locução nos Reels: voz neural, sem música. `montar_reel.py`
continua existindo para o caso de um Reel só de ambiente, mas o caminho normal
é o `montar_reel_narrado.py`.

A inversão é o ponto: no montador de ambiente a cena manda e o áudio segue; no
narrado a **fala manda e a cena é cortada para caber nela**. Cada cena ganha
uma `fala`, o trecho é sintetizado, medido, e a janela de vídeo passa a ser
`ini` até `ini + (lead + voz + tail) × vel`. O `fim` da cena vira só anotação
de curadoria — quem corta é a locução.

```jsonc
"narracao": { "voz": "pt-BR-AntonioNeural", "rate": "+7%",
              "lead": 0.28, "tail": 0.42, "ambiente": 0.22 },
"cenas": [
  { "fonte": "...", "ini": 4.0, "fim": 8.5, "vel": 1.0,
    "espelhar": false,
    "zoom": 1.35, "anchor_x": 0.52, "anchor_y": 1.0,
    "texto": "LOCAÇÃO DE RUAS", "estilo": "label",
    "fala": "A rua ainda não existe. Mas já tem coordenada." }
]
```

`lead`/`tail` são as respirações antes e depois da fala; `ambiente` é o ganho
do som de campo por baixo da voz (0,22 = campo presente sem disputar).
`espelhar` aplica `hflip`: vídeo de câmera frontal sai invertido e a logo da
camisa da equipe aparece de trás para frente — só use em cena sem placa,
painel ou número no quadro, senão o espelho inverte essa informação também.

`zoom`, `anchor_x` e `anchor_y` reenquadram a cena, com a mesma semântica dos
cards: 0 mantém o topo/a esquerda, 1 o rodapé/a direita, 0,5 centraliza. Sem
eles, um plate 16:9 de drone vira sempre o terço central da largura em altura
cheia — e quando o piloto enquadrou o chão, o assunto cai no quinto de baixo,
justo onde a interface do player cobre. `zoom` com `anchor_y: 1.0` corta a
terra morta do topo e sobe o assunto para fora dessa faixa. Duas ressalvas:
recorte estreito não segura assunto que anda (confira o primeiro e o último
quadro da cena, não só o do meio), e `zoom` acima de ~1,6 num plate 4K já
começa a amolecer — aí é melhor `vel` abaixo de 1 para a cena consumir menos
tempo de origem e o assunto não sair do recorte.

Instalação da voz, no venv da empresa:

```powershell
& C:\Users\ALCIO\.ajtopogeo\venv\Scripts\python.exe -m pip install edge-tts
```

Escrever a fala: frases curtas, uma ideia por cena, mesmo tom técnico do resto
da rotina. Conte ~9,5 caracteres por segundo em `+7%` para orçar a duração
antes de gerar. O CTA fecha na cena do topógrafo saindo do serviço, não num
close falando para a câmera. Música **não entra** — se o usuário quiser uma
batida, ele sobe por cima na edição do Instagram, por conta dele.

O guia em PDF ganha a seção "Roteiro da locução" automaticamente quando alguma
cena tem `fala`: quem publica precisa ler o que a voz diz antes de subir.

**Enquadramento da foto de fundo.** `zoom`, `anchor_y` e `anchor_x` valem em
qualquer card (capa, corpo e capa de Reel), não só na capa de Reel. É com eles
que se tira o assunto de trás do bloco de texto: `zoom` amplia, `anchor_y` 0
mantém o topo da foto (empurra o assunto para baixo), 1 mantém o rodapé (puxa
para cima), `anchor_x` faz o mesmo na horizontal. Como o assunto só desce até
`y_original × zoom`, foto com o assunto colado no topo não tem conserto por
enquadramento — troque a foto ou aceite a sobreposição.

## Diagramas

`perfil_mata` — mata em corte. Explica MDS × MDT, altura de dossel, ponto
levantado no chão.
`mds`, `mdt` (bool) · `cota` (texto da medida, ex. `"+15 m"`) ·
`pontos` (bool) · `top` (padrão 780).

`perfil_vertente` — ocupação no platô, mata na encosta, fundo de vale. Serve
para drenagem, terraplenagem, talvegue, APP.
`topo_rotulo` · `agua` (bool) · `curvas` (bool) · `lancamento` (bool) ·
`marcas`: lista de `[posicao_0a1, "TEXTO", "solo|meio|copa"]`.

`corte_via_pv` — corte transversal da via para locação de poço de visita (PV)
de esgoto. Capa asfáltica como faixa na superfície (greide no topo), o fuste
do poço descendo abaixo dela (tubo com anéis e centro tracejado), o tampão em
destaque no nível do greide, e o meio-fio na lateral separando a pista (mais
baixa) do terreno/passeio (mais alto). Uma cota de amarração lateral, em
laranja, liga o centro do poço à face do meio-fio — a referência que sobrevive
ao corte do asfalto. Traz seu próprio degradê de leitura, então funciona sobre
foto clara. Rótulos clampados à margem.
`cota` (texto da medida, ex.: `"amarração lateral ao meio-fio"`) ·
`rotulos`: lista `[capa, fuste, tampão, meio-fio]` (padrão
`["CAPA ASFÁLTICA", "FUSTE DO POÇO", "TAMPÃO NO GREIDE", "MEIO-FIO"]`) ·
`top` (padrão 760).

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

**Sub da capa sumindo na foto.** O degradê do topo em `foto_fundo` morre onde o
título acaba, e a linha de apoio cai logo abaixo — em cima de estrutura
metálica ou concreto claro o cinza do sub some. `marca.faixa_texto()` compõe
uma faixa local esfumada atrás do bloco; `render.py` já chama nas duas capas.
Ela tem que ser composta **antes** de o texto ser pintado: `alpha_composite`
depois escureceria o próprio texto.

**Drone não grava áudio.** O MP4 que sai do cartão do DJI costuma vir só com
vídeo. Pedir `[n:a]` de um arquivo desses derruba o filtergraph inteiro com
`matches no streams`, sem dizer qual arquivo é. `montar_reel.py` detecta a
fonte muda, põe silêncio no lugar, entra a cena seguinte com fade de 0,45 s
para o ambiente não estalar no corte, e avisa quantos segundos ficaram sem
trilha. Se o Reel precisa de som do começo ao fim, grave um ambiente no celular
junto com o voo — nunca música.

**Cena curta demais no Reel narrado.** `overlay=shortest=1` corta a cena inteira
no menor dos dois lados, e um `trim` de vídeo VFR — drone e celular gravam
assim — devolve menos quadros do que a duração pedida. Resultado: a fala
continua e a imagem já pulou. `montar_reel_narrado.py` põe
`tpad=stop_mode=clone` na base de cada cena e um `trim=duration=` depois, então
a base bate a duração exata e o overlay entra sem `shortest`.

**Silêncio da edge-tts.** A voz neural entrega ~0,16 s de silêncio antes e
~0,82 s depois de cada trecho. Como no modo narrado a duração da cena é a
duração do trecho, isso vira quase um segundo de cena parada por fala — seis
segundos num Reel de seis cenas. `_aparar_silencio()` apara as pontas e a
respiração volta controlada por `lead`/`tail`.

**Drone mudo por baixo da locução.** Nas cenas de drone não há ambiente nenhum,
então a pausa entre duas frases da locução fica em silêncio digital absoluto —
não é bug, é o material. O script avisa quantos segundos vêm de fonte muda.
A solução de campo é a mesma de sempre: gravar um ambiente no celular junto com
o voo. Nunca tapar com música.

**Assunto do drone embaixo da interface do player.** O piloto enquadra o chão,
não a moldura 9:16: no plate 16:9 o carro e a equipe ficam no quinto de baixo,
que é justo o que a interface do Reel cobre. Como o recorte 9:16 de um 16:9
usa a altura inteira, não há o que cortar embaixo — quem sobe o assunto é
`zoom` com `anchor_y: 1.0`, que come a terra morta do topo. Confira o último
quadro da cena também: recorte apertado perde assunto que anda.

**Burst de desfoque no meio do trecho do drone.** O DJI dá um solavanco de
refoco de meio segundo em pleno voo, e ele não aparece na contact sheet de
4,8 s. Antes de fixar `ini`, varra a janela com a variância do laplaciano
(passo de 0,25 s): a queda é de 600 para 15, inconfundível. Comparar valores
entre cenas não vale — cena de terra lisa dá variância baixa por falta de
textura, não por desfoque.

**Vídeo de WhatsApp.** Vem em 478×850. Ampliar para 1080×1920 resolve para o
feed mas não recupera detalhe — registre a pendência de pedir o original do
celular. O vídeo que sai do cartão do drone vem em 4K e não tem esse problema.

**Escape de caminho no JSON.** Use barras normais (`C:/Users/...`). O Windows
aceita, e evita a classe inteira de erro de `\U` inválido.

**Tabela do PDF estourando a página.** Toda célula tem que virar `Paragraph`
para quebrar linha — string crua não quebra. Já tratado em `tabela()`.

**Negrito no PDF.** `<b>` só funciona depois de `registerFontFamily`. Já
registrado.
