import cv2
import mediapipe as mp
import math
import time
import random # NOVIDADE: Importamos a biblioteca random

# --- Inicialização ---
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# --- Configurações ---
COR_ALVO = (0, 255, 0)
COR_BOLA = (0, 0, 255)
COR_TEXTO = (255, 255, 255)
COR_FEEDBACK_BOM = (0, 255, 0)
COR_FEEDBACK_RUIM = (0, 0, 255)

PONTUACAO = 0
NIVEL = 1
VELOCIDADE_BOLA_INICIAL = 3.0 # A velocidade base ainda aumenta com o nível
RAIO_ALVO = 40
RAIO_BOLA_MAX = 30

# --- Variáveis de Estado ---
# NOVIDADE: Adicionamos o estado 'INTERVALO'
estado_jogo = 'AGUARDANDO' 
tempo_inicio_feedback = 0
tempo_inicio_intervalo = 0
duracao_intervalo_aleatorio = 0

alvo = {'x': 0, 'y': 0, 'ativo': False}
bola = {'x': 0, 'y': 0, 'raio': 0, 'tempo_inicio': 0}

feedback_msg = ""
cor_feedback = COR_TEXTO

# Variáveis para análise técnica
dist_ombros_maxima = 0
altura_quadril_base = 0
fez_split_step = False
virou_tronco_cedo = False
feedback_tecnico_final = ""

def calcular_distancia(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

# --- Loop Principal ---
cap = cv2.VideoCapture('teste_tenis.mp4') 
print("Iniciando o jogo... Pressione 'q' para sair.")

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
        mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        landmarks = results.pose_landmarks.landmark
        
        # ... (Extração de Pontos) ...
        ombro_d_xy = (int(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].x * w), int(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].y * h))
        ombro_e_xy = (int(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].x * w), int(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].y * h))
        punho_d_xy = (int(landmarks[mp_pose.PoseLandmark.RIGHT_WRIST].x * w), int(landmarks[mp_pose.PoseLandmark.RIGHT_WRIST].y * h))
        quadril_d_y = int(landmarks[mp_pose.PoseLandmark.RIGHT_HIP].y * h)
        quadril_e_y = int(landmarks[mp_pose.PoseLandmark.LEFT_HIP].y * h)
        
        ombro_d_z = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].z
        punho_d_z = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST].z

        centro_corpo_x = (ombro_d_xy[0] + ombro_e_xy[0]) // 2
        dist_ombros_atual = calcular_distancia(ombro_d_xy, ombro_e_xy)
        altura_quadril_atual = (quadril_d_y + quadril_e_y) / 2

        if estado_jogo == 'AGUARDANDO' and dist_ombros_atual > 50:
            fez_split_step = False
            virou_tronco_cedo = False
            feedback_tecnico_final = ""
            
            if dist_ombros_atual > dist_ombros_maxima:
                dist_ombros_maxima = dist_ombros_atual
            
            altura_quadril_base = altura_quadril_atual

            if dist_ombros_maxima > 0:
                alvo['x'] = centro_corpo_x + int(dist_ombros_atual * 1.5)
                alvo['y'] = h // 2
                bola['tempo_inicio'] = time.time()
                estado_jogo = 'JOGANDO'

        elif estado_jogo == 'JOGANDO':
            # ... (Lógica de checagem de preparação técnica) ...
            if not virou_tronco_cedo and dist_ombros_maxima > 0 and (dist_ombros_atual < dist_ombros_maxima * 0.7):
                virou_tronco_cedo = True; PONTUACAO += 15
            if not fez_split_step and altura_quadril_base > 0 and (altura_quadril_atual > altura_quadril_base + 10):
                fez_split_step = True; PONTUACAO += 10
            
            cv2.circle(frame, (alvo['x'], alvo['y']), RAIO_ALVO, COR_ALVO, 3)
            
            # NOVIDADE: Velocidade da bola com variação aleatória
            velocidade_base = max(1.0, VELOCIDADE_BOLA_INICIAL - (NIVEL * 0.2))
            velocidade_atual = velocidade_base - random.uniform(0.0, 0.5) # Variação de até 0.5s

            progresso = (time.time() - bola['tempo_inicio']) / velocidade_atual

            if progresso < 1.0:
                 bola_x_atual = int(w // 2 + (alvo['x'] - w // 2) * progresso)
                 bola_y_atual = int(0 + (alvo['y'] - 0) * progresso)
                 bola_raio_atual = int(RAIO_BOLA_MAX * progresso)
                 cv2.circle(frame, (bola_x_atual, bola_y_atual), bola_raio_atual, COR_BOLA, -1)
            else: # Momento do impacto
                # ... (Lógica de pontuação do impacto) ...
                contato_atrasado = punho_d_z > ombro_d_z
                dist_contato = calcular_distancia(punho_d_xy, (alvo['x'], alvo['y']))
                if contato_atrasado: feedback_msg = "Contato Atrasado!"; cor_feedback = COR_FEEDBACK_RUIM; PONTUACAO -= 30
                elif dist_contato < RAIO_ALVO / 2: feedback_msg = "Perfeito!"; cor_feedback = COR_FEEDBACK_BOM; PONTUACAO += 100; NIVEL += 1
                elif dist_contato < RAIO_ALVO: feedback_msg = "Bom Ajuste!"; cor_feedback = COR_FEEDBACK_BOM; PONTUACAO += 50
                else: feedback_msg = "Longe!"; cor_feedback = COR_FEEDBACK_RUIM; PONTUACAO -= 25

                if not fez_split_step: feedback_tecnico_final += "Lembre do Split Step! "
                if not virou_tronco_cedo: feedback_tecnico_final += "Gire o tronco cedo!"

                estado_jogo = 'FEEDBACK'
                tempo_inicio_feedback = time.time()
                dist_ombros_maxima = 0

        elif estado_jogo == 'FEEDBACK':
            # Exibe o feedback do golpe
            cv2.putText(frame, feedback_msg, (w//2 - 150, h//2), cv2.FONT_HERSHEY_SIMPLEX, 1.5, cor_feedback, 3)
            cv2.putText(frame, feedback_tecnico_final, (w//2 - 300, h//2 + 60), cv2.FONT_HERSHEY_SIMPLEX, 1, COR_TEXTO, 2)
            
            # NOVIDADE: Transição para o estado de INTERVALO após 2 segundos de feedback
            if time.time() - tempo_inicio_feedback > 2.0:
                estado_jogo = 'INTERVALO'
                tempo_inicio_intervalo = time.time()
                # Define um tempo de espera aleatório entre 1.0 e 3.5 segundos para a próxima bola
                duracao_intervalo_aleatorio = random.uniform(1.0, 3.5)
        
        # NOVIDADE: Novo estado de jogo para o intervalo entre as bolas
        elif estado_jogo == 'INTERVALO':
            # Mostra uma mensagem sutil para a jogadora se manter pronta
            cv2.putText(frame, "Prepare-se...", (w//2 - 100, h//2), cv2.FONT_HERSHEY_SIMPLEX, 1, COR_TEXTO, 2)
            
            # Espera o tempo aleatório passar
            if time.time() - tempo_inicio_intervalo > duracao_intervalo_aleatorio:
                estado_jogo = 'AGUARDANDO'

    # --- Desenhar informações na tela ---
    cv2.putText(frame, f"Pontos: {PONTUACAO}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, COR_TEXTO, 2)
    cv2.putText(frame, f"Nivel: {NIVEL}", (w - 200, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, COR_TEXTO, 2)
    
    if estado_jogo == 'JOGANDO':
        if virou_tronco_cedo: cv2.putText(frame, "Giro do Tronco ✔", (30, h - 70), cv2.FONT_HERSHEY_SIMPLEX, 1, COR_FEEDBACK_BOM, 2)
        if fez_split_step: cv2.putText(frame, "Split Step ✔", (30, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 1, COR_FEEDBACK_BOM, 2)

    cv2.imshow('Jogo de Tenis VR - Treino de Footwork', frame)
    if cv2.waitKey(5) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()