import os
import time
import json
import re
import google.generativeai as genai
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, vfx
from PIL import Image # <--- Importante para o novo preview rápido
import numpy as np

# --- CLASSE 1: PROCESSADOR DE CORTES (MANTIDA IGUAL) ---
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
        if status_callback: status_callback("Enviando vídeo (Imagem + Áudio) para o Google Gemini...")
        try:
            video_file = genai.upload_file(path=video_path)
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            if video_file.state.name == "FAILED": raise Exception("Falha no Google.")
            
            if status_callback: status_callback("IA a analisar o vídeo...")

            base_prompt = """
            Analise este vídeo de forma MULTIMODAL.
            ORDEM DO USUÁRIO: "{user_orders}"
            Retorne APENAS JSON: [{{"inicio": "MM:SS", "fim": "MM:SS", "titulo_arquivo": "Titulo"}}]
            """
            prompt_final = base_prompt.format(user_orders=user_orders if user_orders else "Padrao: Title Cards")
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content([video_file, prompt_final], request_options={"timeout": 600})
            return self._clean_json_response(response.text)
        except Exception as e:
            print(f"Erro: {e}")
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
        output_dir = "cortes_temp"
        if not os.path.exists(output_dir): os.makedirs(output_dir)

        for i, cut in enumerate(cuts_data):
            try:
                start = self._time_to_seconds(cut['inicio'])
                end = self._time_to_seconds(cut['fim'])
                safe_title = "".join([c for c in cut['titulo_arquivo'] if c.isalnum()]).strip()[:20]
                filename = os.path.join(output_dir, f"Corte_{i+1}_{safe_title}.mp4")
                if end > clip.duration: end = clip.duration
                if end <= start: continue
                sub = clip.subclip(start, end)
                if speed_factor != 1.0: sub = sub.fx(vfx.speedx, speed_factor)
                sub.write_videofile(filename, codec="libx264", audio_codec="aac", preset='ultrafast', logger=None)
                generated_files.append(filename)
                if progress_callback: progress_callback((i+1)/len(cuts_data))
            except: pass
        clip.close()
        return generated_files

# --- CLASSE 2: PROCESSADOR DE TEMPLATES (ATUALIZADA E BLINDADA) ---
class TemplateProcessor:
    def __init__(self):
        pass

    def get_preview_frame(self, video_path, template_path, y_offset):
        """
        Gera o preview usando PIL (Pillow) em vez de MoviePy.
        Muito mais rápido e sem erros de renderização.
        """
        try:
            # 1. Extrai frame do vídeo (usando MoviePy apenas para leitura)
            clip = VideoFileClip(video_path)
            frame_array = clip.get_frame(clip.duration / 2) # Pega frame do meio
            clip.close() # Fecha logo para não ocupar memória

            # 2. Converte para Imagem PIL
            video_img = Image.fromarray(frame_array)
            template_img = Image.open(template_path).convert("RGBA")

            # 3. Ajusta o tamanho do Template para a largura do vídeo
            target_width = video_img.width
            ratio = target_width / float(template_img.width)
            target_height = int(float(template_img.height) * float(ratio))
            
            # Redimensiona o template com alta qualidade
            template_img = template_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # 4. Cria um Canvas (Fundo Transparente) do tamanho do Template
            # O template define o tamanho final do vídeo vertical (shorts)
            canvas = Image.new('RGBA', template_img.size, (0,0,0,0))

            # 5. Cola o vídeo (Fundo) na posição escolhida
            # Centraliza horizontalmente: (LarguraCanvas - LarguraVideo) / 2
            x_pos = (canvas.width - video_img.width) // 2
            canvas.paste(video_img, (x_pos, y_offset))

            # 6. Cola o Template (Moldura) por cima
            # O terceiro argumento serve como máscara de transparência
            canvas.paste(template_img, (0, 0), template_img)

            return canvas

        except Exception as e:
            print(f"Erro detalhado no preview: {e}")
            return None

    def render_video_with_template(self, video_path, template_path, y_offset, progress_callback=None):
        try:
            clip = VideoFileClip(video_path)
            template = ImageClip(template_path).set_duration(clip.duration)
            
            if template.w != clip.w:
                template = template.resize(width=clip.w)
            
            # Aplica a posição ajustada no preview
            clip_positioned = clip.set_position(("center", y_offset))
            template_positioned = template.set_position("center")
            
            final = CompositeVideoClip([clip_positioned, template_positioned], size=template.size)
            output_path = f"template_output_{int(time.time())}.mp4"
            
            if progress_callback: progress_callback(0.2, "Renderizando vídeo final (isso pode demorar)...")
            
            final.write_videofile(output_path, codec="libx264", audio_codec="aac", preset="ultrafast", logger=None)
            
            clip.close()
            template.close()
            final.close()
            return output_path
        except Exception as e:
            print(f"Erro render: {e}")
            return None
