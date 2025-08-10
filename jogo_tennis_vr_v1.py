import cv2
import mediapipe as mp
import math
import time

# --- Inicialização das ferramentas ---
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# --- Configurações do Jogo ---
COR_ALVO = (0, 255, 0)
COR_BOLA = (0, 0, 255)
COR_TEXTO = (255, 255, 255)
COR_FEEDBACK_BOM = (0, 255, 0)
COR_FEEDBACK_RUIM = (0, 0, 255)

PONTUACAO = 0
NIVEL = 1
VELOCIDADE_BOLA_INICIAL = 3.0
RAIO_ALVO = 40
RAIO_BOLA_MAX = 30

estado_jogo = 'AGUARDANDO'
tempo_inicio_feedback = 0

alvo = {'x': 0, 'y': 0, 'ativo': False}
bola = {'x': 0, 'y': 0, 'raio': 0, 'tempo_inicio': 0}

feedback_msg = ""
cor_feedback = COR_TEXTO

def calcular_distancia(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

# --- Loop Principal do Jogo ---
cap = cv2.VideoCapture('teste_tenis.mp4') 

print("Iniciando o jogo a partir de um arquivo de vídeo...")
print("Pressione 'q' para sair.")

while cap.isOpened():
    success, frame = cap.read()
    
    if not success:
        print("Vídeo terminou. Reiniciando...")
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    frame = cv2.flip(frame, 1)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    results = pose.process(frame_rgb)
    
    h, w, _ = frame.shape

    if results.pose_landmarks:
        mp_drawing.draw_landmarks(
            frame,
            results.pose_landmarks,
            mp_pose.POSE_CONNECTIONS)

        landmarks = results.pose_landmarks.landmark
        
        # Coletando coordenadas X e Y
        ombro_direito_xy = (int(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].x * w),
                            int(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].y * h))
        ombro_esquedro_xy = (int(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].x * w),
                             int(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].y * h))
        punho_direito_xy = (int(landmarks[mp_pose.PoseLandmark.RIGHT_WRIST].x * w),
                            int(landmarks[mp_pose.PoseLandmark.RIGHT_WRIST].y * h))
        
        # NOVIDADE: Coletando a coordenada Z para checar a profundidade
        ombro_direito_z = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].z
        punho_direito_z = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST].z

        centro_corpo_x = (ombro_direito_xy[0] + ombro_esquedro_xy[0]) // 2
        dist_ombros = calcular_distancia(ombro_direito_xy, ombro_esquedro_xy)

        if estado_jogo == 'AGUARDANDO' and dist_ombros > 50:
            alvo['x'] = centro_corpo_x + int(dist_ombros * 1.5)
            alvo['y'] = h // 2
            alvo['ativo'] = True
            bola['x'] = w // 2
            bola['y'] = 0
            bola['tempo_inicio'] = time.time()
            bola['raio'] = 5
            estado_jogo = 'JOGANDO'

        elif estado_jogo == 'JOGANDO':
            cv2.circle(frame, (alvo['x'], alvo['y']), RAIO_ALVO, COR_ALVO, 3)
            velocidade_atual = max(1.0, VELOCIDADE_BOLA_INICIAL - (NIVEL * 0.2))
            progresso = (time.time() - bola['tempo_inicio']) / velocidade_atual

            if progresso < 1.0:
                bola_x_atual = int(bola['x'] + (alvo['x'] - bola['x']) * progresso)
                bola_y_atual = int(bola['y'] + (alvo['y'] - bola['y']) * progresso)
                bola_raio_atual = int(bola['raio'] + (RAIO_BOLA_MAX - bola['raio']) * progresso)
                cv2.circle(frame, (bola_x_atual, bola_y_atual), bola_raio_atual, COR_BOLA, -1)
            else: # Momento do impacto
                dist_contato = calcular_distancia(punho_direito_xy, (alvo['x'], alvo['y']))
                dist_punho_ombro = calcular_distancia(punho_direito_xy, ombro_direito_xy)
                foi_esticada = dist_punho_ombro > dist_ombros * 1.2
                
                # NOVIDADE: Verificação de contato atrasado usando a coordenada Z
                contato_atrasado = punho_direito_z > ombro_direito_z
                
                # NOVIDADE: Lógica de feedback prioriza o erro de contato atrasado
                if contato_atrasado:
                    PONTUACAO -= 30  # Penalidade severa por contato atrasado
                    feedback_msg = "Contato Atrasado!"
                    cor_feedback = COR_FEEDBACK_RUIM
                elif dist_contato < RAIO_ALVO / 2:
                    PONTUACAO += 100
                    feedback_msg = "Perfeito!"
                    cor_feedback = COR_FEEDBACK_BOM
                    NIVEL += 1
                elif dist_contato < RAIO_ALVO:
                    PONTUACAO += 50
                    feedback_msg = "Bom Ajuste!"
                    cor_feedback = COR_FEEDBACK_BOM
                else: # Errou o alvo em 2D
                    PONTUACAO -= 25
                    cor_feedback = COR_FEEDBACK_RUIM
                    if foi_esticada:
                        feedback_msg = "Mova os pes!"
                    else:
                        feedback_msg = "Longe!"

                PONTUACAO = max(0, PONTUACAO)
                estado_jogo = 'FEEDBACK'
                tempo_inicio_feedback = time.time()

        elif estado_jogo == 'FEEDBACK':
            # Ajustando o tamanho da fonte para caber melhor na tela
            (text_width, text_height), _ = cv2.getTextSize(feedback_msg, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)
            text_x = (w - text_width) // 2
            cv2.putText(frame, feedback_msg, (text_x, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.5, cor_feedback, 3)
            
            if time.time() - tempo_inicio_feedback > 2:
                estado_jogo = 'AGUARDANDO'

    cv2.putText(frame, f"Pontos: {PONTUACAO}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, COR_TEXTO, 2)
    cv2.putText(frame, f"Nivel: {NIVEL}", (w - 150, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, COR_TEXTO, 2)
    cv2.imshow('Jogo de Tenis VR - Treino de Footwork', frame)

    if cv2.waitKey(5) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()