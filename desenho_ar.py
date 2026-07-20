"""
Desenho AR - Desenhe no ar usando a webcam e os gestos da mão.

Gestos:
  - So o indicador levantado        -> modo DESENHO
    (a espessura do traco varia com a distancia da mao ate a camera:
     mao mais perto = traco mais grosso)
  - Indicador + medio levantados    -> modo MOVER (arrasta o desenho inteiro)
  - Indicador + mindinho levantados -> modo ZOOM
    (mover a mao pra CIMA aumenta o desenho, pra BAIXO diminui)
  - Mao aberta (4+ dedos)           -> LIMPAR tela
  - Mao fechada (nenhum dedo)       -> PAUSA

Teclas:
  - 'z' -> desfaz a ultima acao (undo)
  - 's' -> salva o desenho atual como PNG
  - 'c' -> limpa a tela
  - 'q' -> sai do programa
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import os

# ---------------------------------------------------------------------------
# Configuracao inicial
# ---------------------------------------------------------------------------

LARGURA, ALTURA = 1280, 720

# Paleta de cores (nome, cor em BGR)
CORES = [
    ("Vermelho", (0, 0, 255)),
    ("Verde", (0, 255, 0)),
    ("Azul", (255, 0, 0)),
    ("Amarelo", (0, 255, 255)),
    ("Roxo", (255, 0, 255)),
    ("Branco", (255, 255, 255)),
]
ALTURA_BARRA = 80  # altura da barra de cores no topo

# Espessura do traco: varia entre esses limites conforme a distancia da mao
ESPESSURA_MIN = 3
ESPESSURA_MAX = 28
# Distancia (em pixels na imagem) entre pulso e base do dedo medio:
# valores tipicos de calibracao - ajuste se a espessura nao variar bem.
DIST_MAO_LONGE = 70
DIST_MAO_PERTO = 200

# Zoom: quanto de deslocamento vertical (px) equivale a 100% de mudanca de escala
SENSIBILIDADE_ZOOM = 250
ESCALA_MIN, ESCALA_MAX = 0.3, 3.0

TAMANHO_HISTORICO = 20

mp_hands = mp.solutions.hands
mp_desenho = mp.solutions.drawing_utils
mp_estilos = mp.solutions.drawing_styles


def dedos_levantados(landmarks, mao_label):
    """
    Retorna uma lista de 5 booleanos indicando se cada dedo esta levantado.
    Ordem: [polegar, indicador, medio, anelar, mindinho]
    """
    pontos = landmarks.landmark
    estados = []

    # Polegar: compara posicao x da ponta com a da articulacao anterior,
    # invertendo dependendo de ser mao direita ou esquerda (imagem espelhada).
    if mao_label == "Right":
        estados.append(pontos[4].x < pontos[3].x)
    else:
        estados.append(pontos[4].x > pontos[3].x)

    # Demais dedos: ponta acima da articulacao intermediaria (PIP) = levantado
    pontas = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    for ponta, pip in zip(pontas, pips):
        estados.append(pontos[ponta].y < pontos[pip].y)

    return estados


def calcular_espessura(landmarks):
    """
    Estima a 'proximidade' da mao com base na distancia, em pixels,
    entre o pulso (landmark 0) e a base do dedo medio (landmark 9).
    Quanto mais perto da camera, maior essa distancia na imagem.
    """
    pulso = landmarks.landmark[0]
    base_medio = landmarks.landmark[9]

    dx = (pulso.x - base_medio.x) * LARGURA
    dy = (pulso.y - base_medio.y) * ALTURA
    distancia = (dx ** 2 + dy ** 2) ** 0.5

    espessura = np.interp(
        distancia, [DIST_MAO_LONGE, DIST_MAO_PERTO], [ESPESSURA_MIN, ESPESSURA_MAX]
    )
    return int(np.clip(espessura, ESPESSURA_MIN, ESPESSURA_MAX))


def desenhar_barra_cores(frame, cor_selecionada_idx):
    """Desenha a barra de selecao de cores no topo do frame."""
    largura_bloco = LARGURA // (len(CORES) + 1)  # +1 para o bloco de "limpar"

    for i, (nome, cor) in enumerate(CORES):
        x_inicio = i * largura_bloco
        x_fim = x_inicio + largura_bloco
        cv2.rectangle(frame, (x_inicio, 0), (x_fim, ALTURA_BARRA), cor, -1)
        if i == cor_selecionada_idx:
            cv2.rectangle(frame, (x_inicio, 0), (x_fim, ALTURA_BARRA), (0, 0, 0), 4)

    # Bloco final = limpar tela
    x_inicio = len(CORES) * largura_bloco
    cv2.rectangle(frame, (x_inicio, 0), (LARGURA, ALTURA_BARRA), (50, 50, 50), -1)
    cv2.putText(frame, "LIMPAR", (x_inicio + 15, 45), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (255, 255, 255), 2)

    return largura_bloco


def empilhar_historico(historico, canvas):
    """Guarda uma copia do canvas atual na pilha de undo."""
    historico.append(canvas.copy())
    if len(historico) > TAMANHO_HISTORICO:
        historico.pop(0)


def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, LARGURA)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTURA)

    if not cap.isOpened():
        print("Erro: nao foi possivel abrir a webcam.")
        return

    canvas = np.zeros((ALTURA, LARGURA, 3), dtype=np.uint8)
    historico = []  # pilha de undo

    cor_idx = 0
    ponto_anterior = None
    modo_atual = "PAUSA"
    modo_anterior = "PAUSA"

    # Estado do arraste (gesto indicador + medio)
    ponto_inicio_arrasto = None
    canvas_inicio_arrasto = None

    # Estado do zoom (gesto indicador + mindinho)
    ponto_inicio_zoom = None
    canvas_inicio_zoom = None

    pasta_saidas = os.path.join(os.path.dirname(os.path.abspath(__file__)), "desenhos_salvos")
    os.makedirs(pasta_saidas, exist_ok=True)

    with mp_hands.Hands(
        model_complexity=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.6,
        max_num_hands=1,
    ) as hands:

        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                print("Nao foi possivel ler o frame da webcam.")
                break

            frame = cv2.flip(frame, 1)
            frame = cv2.resize(frame, (LARGURA, ALTURA))

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resultado = hands.process(rgb)

            largura_bloco = desenhar_barra_cores(frame, cor_idx)

            if resultado.multi_hand_landmarks and resultado.multi_handedness:
                landmarks = resultado.multi_hand_landmarks[0]
                mao_label = resultado.multi_handedness[0].classification[0].label

                mp_desenho.draw_landmarks(
                    frame, landmarks, mp_hands.HAND_CONNECTIONS,
                    mp_estilos.get_default_hand_landmarks_style(),
                    mp_estilos.get_default_hand_connections_style(),
                )

                dedos = dedos_levantados(landmarks, mao_label)
                qtd_levantados = sum(dedos)
                espessura_atual = calcular_espessura(landmarks)

                ponta_indicador = landmarks.landmark[8]
                x = int(ponta_indicador.x * LARGURA)
                y = int(ponta_indicador.y * ALTURA)

                # --- 1) Decide o modo (sem efeitos colaterais ainda) -------
                if y < ALTURA_BARRA:
                    modo_atual = "SELECIONANDO"
                elif dedos == [False, True, False, False, False]:
                    modo_atual = "DESENHANDO"
                elif dedos[1] and dedos[2] and not dedos[3] and not dedos[4]:
                    modo_atual = "MOVENDO"
                elif dedos == [False, True, False, False, True]:
                    modo_atual = "ZOOM"
                elif qtd_levantados >= 4:
                    modo_atual = "LIMPANDO"
                else:
                    modo_atual = "PAUSA"

                inicio_gesto = (modo_atual != modo_anterior)

                # --- 2) Aplica os efeitos de cada modo ----------------------
                if modo_atual == "SELECIONANDO":
                    bloco = x // largura_bloco
                    if bloco < len(CORES):
                        cor_idx = bloco
                    else:
                        if inicio_gesto:
                            empilhar_historico(historico, canvas)
                        canvas[:] = 0
                    ponto_anterior = None

                elif modo_atual == "DESENHANDO":
                    if inicio_gesto:
                        empilhar_historico(historico, canvas)
                        ponto_anterior = None
                    if ponto_anterior is not None:
                        cv2.line(canvas, ponto_anterior, (x, y),
                                  CORES[cor_idx][1], espessura_atual)
                    ponto_anterior = (x, y)
                    cv2.circle(frame, (x, y), espessura_atual // 2 + 2,
                               CORES[cor_idx][1], -1)

                elif modo_atual == "MOVENDO":
                    ponto_anterior = None
                    if inicio_gesto:
                        empilhar_historico(historico, canvas)
                        ponto_inicio_arrasto = (x, y)
                        canvas_inicio_arrasto = canvas.copy()
                    else:
                        dx = x - ponto_inicio_arrasto[0]
                        dy = y - ponto_inicio_arrasto[1]
                        matriz = np.float32([[1, 0, dx], [0, 1, dy]])
                        canvas = cv2.warpAffine(
                            canvas_inicio_arrasto, matriz, (LARGURA, ALTURA)
                        )
                    cv2.circle(frame, (x, y), 12, (200, 200, 200), 2)

                elif modo_atual == "ZOOM":
                    ponto_anterior = None
                    if inicio_gesto:
                        empilhar_historico(historico, canvas)
                        ponto_inicio_zoom = (x, y)
                        canvas_inicio_zoom = canvas.copy()
                    else:
                        # Mover pra cima (y diminui) deve AUMENTAR a escala
                        delta_y = ponto_inicio_zoom[1] - y
                        escala = 1 + (delta_y / SENSIBILIDADE_ZOOM)
                        escala = float(np.clip(escala, ESCALA_MIN, ESCALA_MAX))
                        matriz = cv2.getRotationMatrix2D(
                            ponto_inicio_zoom, 0, escala
                        )
                        canvas = cv2.warpAffine(
                            canvas_inicio_zoom, matriz, (LARGURA, ALTURA)
                        )
                        cv2.putText(frame, f"{escala:.2f}x",
                                    (x + 20, y), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.8, (255, 255, 255), 2)
                    cv2.circle(frame, (x, y), 12, (0, 200, 255), 2)

                elif modo_atual == "LIMPANDO":
                    if inicio_gesto:
                        empilhar_historico(historico, canvas)
                    canvas[:] = 0
                    ponto_anterior = None

                else:  # PAUSA
                    ponto_anterior = None

                modo_anterior = modo_atual
            else:
                modo_atual = "SEM MAO DETECTADA"
                modo_anterior = modo_atual
                ponto_anterior = None

            # Combina o canvas de desenho com a imagem da camera
            cinza_canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
            _, mascara = cv2.threshold(cinza_canvas, 10, 255, cv2.THRESH_BINARY)
            mascara_inv = cv2.bitwise_not(mascara)
            fundo = cv2.bitwise_and(frame, frame, mask=mascara_inv)
            frame_final = cv2.add(fundo, canvas)

            cv2.putText(frame_final, f"Modo: {modo_atual}", (10, ALTURA - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame_final, "z=desfazer  s=salvar  c=limpar  q=sair",
                        (10, ALTURA - 50), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (200, 200, 200), 2)

            cv2.imshow("Desenho AR", frame_final)

            tecla = cv2.waitKey(1) & 0xFF
            if tecla == ord('q'):
                break
            elif tecla == ord('c'):
                empilhar_historico(historico, canvas)
                canvas[:] = 0
            elif tecla == ord('z'):
                if historico:
                    canvas = historico.pop()
                    print("Acao desfeita.")
                else:
                    print("Nada para desfazer.")
            elif tecla == ord('s'):
                nome_arquivo = os.path.join(
                    pasta_saidas, f"desenho_{int(time.time())}.png"
                )
                cv2.imwrite(nome_arquivo, canvas)
                print(f"Desenho salvo em: {nome_arquivo}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()