---
name: conteudo-instagram
description: Gera automaticamente as peças de Instagram do @aj_topogeo a partir das fotos/vídeos de campo e da descrição do serviço — triagem de sigilo, legendas, hashtags, cards do carrossel, Reel narrado com voz neural sobre som ambiente (nunca música) e guia de publicação em PDF. Use nas quartas e sextas, ou quando o usuário mandar material de campo pedindo post, legenda ou pauta.
---

# Rotina 5 — Conteúdo Instagram (@aj_topogeo)

Cadência: quarta e sexta. Objetivo: presença digital ativa sem tirar tempo da
execução técnica.

**Esta rotina roda inteira sem perguntar nada.** O usuário manda o material e a
descrição do serviço; você devolve tudo pronto para postar. Não pergunte qual
eixo usar, quantas peças fazer, qual foto escolher ou se pode prosseguir —
decida e execute. A única coisa que você não faz é publicar.

## Entrada

Um zip, uma pasta ou arquivos soltos de fotos e vídeos, mais uma linha
descrevendo o serviço. Se não vier material novo, trabalhe temas gerais a
partir dos `blog-*.html` na raiz do repositório.

Se a descrição do serviço não bater com o que as imagens mostram, siga o que as
imagens mostram e diga isso no relatório final — a descrição costuma ser o
título do serviço, não o enquadramento das fotos.

## Ambiente

Todos os scripts rodam no venv da empresa:

```
C:\Users\ALCIO\.ajtopogeo\venv\Scripts\python.exe
```

Scripts e esquema do `pauta.json` em `scripts/README.md` (leia antes).

## As três etapas

Delegue cada etapa ao subagente correspondente, em sequência, passando o
resultado da anterior. Rode uma de cada vez: a redação depende do inventário e
a edição depende da pauta.

| Etapa | Subagente | Modelo | Entrega |
|---|---|---|---|
| 1. Curadoria | `ig-curadoria` | Sonnet | Inventário do material, recortes seguros, trechos de vídeo com tempos |
| 2. Redação | `ig-redacao` | Sonnet | `pauta.json` com legendas, hashtags, cards e cenas |
| 3. Edição | `ig-edicao` | Opus | Cards, Reel, capa, PDF — conferidos visualmente |

Ao chamar cada um, passe o caminho da pasta de trabalho, o texto do serviço e o
retorno da etapa anterior por inteiro. Subagente começa sem contexto: o que não
estiver no prompt, ele não sabe.

Depois da etapa 3, rode `registrar.py pauta.json` para acrescentar a sessão à
pauta do mês, se a edição ainda não tiver rodado.

## Onde as coisas ficam

| O quê | Onde |
|---|---|
| Material pronto para postar | `C:\Users\ALCIO\Pictures\POST_<SERVICO>_<AAAA-MM-DD>\` |
| Pauta do mês | `G:\Meu Drive\EMPRESA\AJ TOPOGEO\_ROTINAS\INSTAGRAM\AAAA-MM-pauta.md` |
| Trabalho intermediário | pasta de scratchpad da sessão |

A pauta do mês é a memória da rotina: é ela que impede repetir gancho, tema ou
foto. A etapa de redação tem que ler antes de escrever.

## Sigilo do cliente — inegociável

Nunca publique nome de proprietário, número de matrícula, coordenada, valor de
serviço ou imagem que identifique a propriedade: horizonte com silhueta da
cidade, malha reconhecível de loteamento, sede, benfeitoria, placa de veículo,
fachada, marca de gado. Em case, use "uma fazenda em Sidrolândia", "um cliente
da região de Maracaju".

Na dúvida sobre um enquadramento, corte. `recortar.py` existe para isso, e o
recorte gerado tem que ser conferido olhando, não presumido.

## Identidade visual

Cores e tipografia saem do `css/style.css` do site, já codificadas em
`scripts/marca.py`. Não use o conector Canva: as artes são geradas pelos
scripts, que dão controle de layout e reprodutibilidade que o Canva não dá.
A logo de `gestor/LOGO.png` não serve para os cards — é texto preto sobre fundo
branco e some no azul-marinho. A assinatura é tipográfica.

## O que entregar ao usuário no final

Um resumo em prosa com: o que foi gerado e onde, o gancho de cada peça, o que
foi bloqueado por sigilo e por quê, as pendências técnicas, e as decisões que
dependem dele (cidade nas hashtags, qualquer frase que possa soar como crítica
ao cliente, case em andamento vs. entregue). Aponte o PDF como o documento que
ele lê antes de postar.

## Limite

Você escreve, desenha e monta. Quem posta é o usuário. Não publique, não agende
e não suba nada para lugar nenhum.
