<<<<<<< HEAD
# Desenho AR - Desenhe no ar com gestos da mão

Programa em Python que usa a webcam para rastrear sua mão (via MediaPipe) e
permite desenhar na tela usando o dedo indicador, tipo um quadro digital.

## Instalação

Precisa do Python 3.9 a 3.11 (o MediaPipe ainda não suporta bem versões mais
novas do Python em todos os sistemas). Recomendo criar um ambiente virtual:

```bash
cd desenho_ar
python -m venv venv

# Ativar o ambiente virtual
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

## Como rodar

```bash
python desenho_ar.py
```

Uma janela vai abrir mostrando a imagem da sua webcam.

## Gestos


Só o indicador levantado | Modo **desenho** — a ponta do dedo pinta na tela. A espessura do traço varia com a distância da sua mão até a câmera (mais perto = traço mais grosso) 

Indicador + médio levantados | Modo **mover** — arrasta o desenho inteiro pela tela 

Indicador + mindinho levantados | Modo **zoom** — mover a mão pra cima aumenta o desenho, pra baixo diminui 

Mão aberta (4+ dedos) | **Limpa** a tela 

Mão fechada | **Pausa** 

Tocar a barra de cores no topo | Troca a cor do traço 

Tocar o bloco "LIMPAR" na barra | Limpa a tela |

## Teclas

- `z` — desfaz a última ação (undo — funciona pra traços, arrastos, zoom e limpezas)
- `s` — salva o desenho atual como PNG (em `desenhos_salvos/`)
- `c` — limpa a tela
- `q` — sai do programa

## Possíveis ajustes

- **Espessura do traço**: controlada por `ESPESSURA_MIN`, `ESPESSURA_MAX`,
  `DIST_MAO_LONGE` e `DIST_MAO_PERTO`. Se a espessura não variar bem com a
  distância da sua mão, ajuste `DIST_MAO_LONGE`/`DIST_MAO_PERTO` — o programa
  mostra a "distância" calculada se você imprimir a variável `distancia`
  dentro de `calcular_espessura` pra calibrar.

- **Sensibilidade do zoom**: `SENSIBILIDADE_ZOOM` — valores menores tornam o
  zoom mais sensível ao movimento da mão. `ESCALA_MIN`/`ESCALA_MAX` limitam
  o quanto o desenho pode encolher ou crescer.

- **Tamanho do histórico de undo**: `TAMANHO_HISTORICO` — quantos passos
  para trás o `z` consegue voltar.

- **Cores da paleta**: edite a lista `CORES` (cada item é `(nome, cor_BGR)`).

- **Suavizar o traço**: se a linha ficar tremida, dá pra aplicar uma média
  móvel nas coordenadas da ponta do dedo antes de desenhar — posso te ajudar
  a implementar isso se quiser.

- **Detectar mais de uma mão**: mude `max_num_hands=1` para `2` em
  `mp_hands.Hands(...)`.

## Como funciona (resumo técnico)

1. O **MediaPipe Hands** detecta 21 pontos (landmarks) da mão a cada frame.

2. A função `dedos_levantados` compara a posição Y da ponta de cada dedo com
   a da articulação anterior (PIP) para saber se ele está esticado ou dobrado
   — e faz um tratamento especial pro polegar, que se move mais no eixo X.

3. O programa primeiro decide o "modo" (desenhar, mover, zoom, limpar, pausa)
   olhando só pra combinação de dedos levantados, e só depois aplica os
   efeitos — isso permite detectar o **início** de cada gesto comparando com
   o modo do frame anterior (`inicio_gesto`), o que é usado tanto pra tirar
   uma "foto" do canvas antes de arrastar/dar zoom quanto pra alimentar o
   histórico de undo.

4. **Arrastar** e **zoom** funcionam do mesmo jeito: no primeiro frame do
   gesto, guardam uma cópia do canvas e a posição inicial do dedo. Nos
   frames seguintes, aplicam uma transformação (`cv2.warpAffine` para
   translação, `cv2.getRotationMatrix2D` para escala) sempre a partir dessa
   cópia original — assim o desenho não perde qualidade a cada frame.

5. **Espessura do traço**: a função `calcular_espessura` mede a distância,
   em pixels na imagem, entre o pulso e a base do dedo médio. Como a mão
   "aparenta" ser maior na imagem quanto mais perto da câmera ela está, essa
   distância cresce — e o programa usa `np.interp` pra mapear isso numa
   espessura de traço proporcional.

6. **Undo**: toda vez que um gesto de ação começa (novo traço, arrasto, zoom
   ou limpeza), o estado do canvas *antes* da mudança é empilhado em
   `historico`. A tecla `z` desempilha e restaura o canvas anterior.

7. O desenho fica guardado num `canvas` (imagem separada, preta), que depois
   é combinado com o frame da câmera usando uma máscara — assim o traço fica
   "colado" na tela mesmo quando a câmera se move.
=======
# DesenhoAr
Desenhe no ar usando só a webcam e os gestos da mão — sem mouse, sem caneta, sem toque. Feito com Python, OpenCV e MediaPipe.
>>>>>>> cbcdb021a5504eedbebe3ca3671232c70d0ebee7
