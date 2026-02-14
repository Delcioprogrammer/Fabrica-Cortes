import os
import time
import json
import re
import google.generativeai as genai
from moviepy.editor import VideoFileClip, vfx

class VideoProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        genai.configure(api_key=self.api_key)
        self.model_name = 'models/gemini-1.5-flash'

    def _clean_json_response(self, text):
        try:
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            else:
                clean_text = text.replace("```json", "").replace("```", "").strip()
                return json.loads(clean_text)
        except:
            return []

    def upload_and_analyze(self, video_path, user_orders="", status_callback=None):
        """
        Envia o vídeo para o Gemini com instruções para usar VISÃO e AUDIÇÃO.
        """
        if status_callback: status_callback("Enviando vídeo (Imagem + Áudio) para o Google Gemini...")
        
        try:
            video_file = genai.upload_file(path=video_path)
            
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name == "FAILED":
                raise Exception("Falha no processamento do vídeo pelo Google.")

            if status_callback: status_callback("IA assistindo e ouvindo o vídeo para encontrar os cortes...")

            # --- O NOVO PROMPT "COM SENTIDOS" ---
            base_prompt = """
            Você é um Editor de Vídeo Profissional e Inteligente.
            
            SUA MISSÃO:
            Analise este vídeo de forma MULTIMODAL (Use seus 'olhos' para ver a ação e seus 'ouvidos' para entender a fala, o tom de voz e a música).
            
            ORDEM DO USUÁRIO (Prioridade Máxima):
            "{user_orders}"
            
            INSTRUÇÕES DE LÓGICA:
            1. Se o usuário pediu algo específico (ex: "partes engraçadas", "gols", "dicas"), use o áudio e vídeo para encontrar esses momentos exatos.
            2. Se o pedido do usuário for VAZIO, use o modo padrão: Identifique segmentos separados por Telas Pretas (Title Cards).
            3. Seja preciso nos tempos de inicio e fim. Não corte a fala no meio.
            
            FORMATO DE RESPOSTA OBRIGATÓRIO (JSON PURO):
            Retorne APENAS uma lista JSON. Nada de texto antes ou depois.
            [
              {{"inicio": "MM:SS", "fim": "MM:SS", "titulo_arquivo": "Resumo do que acontece"}}
            ]
            """
            
            # Formata o prompt inserindo a ordem do usuário
            prompt_final = base_prompt.format(user_orders=user_orders if user_orders else "Nenhuma ordem específica. Use o padrão de Telas Pretas.")
            
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content([video_file, prompt_final], request_options={"timeout": 600})
            
            return self._clean_json_response(response.text)

        except Exception as e:
            print(f"Erro na análise: {e}")
            return []

    def _time_to_seconds(self, time_str):
        try:
            p = list(map(int, time_str.split(':')))
            if len(p) == 2: return p[0]*60 + p[1]
            elif len(p) == 3: return p[0]*3600 + p[1]*60 + p[2]
            return 0
        except: return 0

    def process_cuts(self, video_path, cuts_data, speed_factor=1.1, progress_callback=None):
        clip = VideoFileClip(video_path)
        generated_files = []
        
        # Cria pasta temporária
        output_dir = "cortes_temp"
        if not os.path.exists(output_dir): os.makedirs(output_dir)

        for i, cut in enumerate(cuts_data):
            try:
                start = self._time_to_seconds(cut['inicio'])
                end = self._time_to_seconds(cut['fim'])
                safe_title = "".join([c for c in cut['titulo_arquivo'] if c.isalnum()]).strip()[:30]
                filename = os.path.join(output_dir, f"Corte_{i+1}_{safe_title}.mp4")

                if end > clip.duration: end = clip.duration
                if end <= start: continue

                sub = clip.subclip(start, end)
                if speed_factor != 1.0:
                    sub = sub.fx(vfx.speedx, speed_factor)
                
                sub.write_videofile(filename, codec="libx264", audio_codec="aac", preset='ultrafast', logger=None)
                generated_files.append(filename)
                
                if progress_callback: progress_callback((i+1)/len(cuts_data))
            except: pass
            
        clip.close()
        return generated_files
