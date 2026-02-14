import os
import time
import json
import re
import google.generativeai as genai
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, vfx
from PIL import Image
import numpy as np

# --- CLASSE 1: PROCESSADOR DE CORTES (IA) ---
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
        if status_callback: status_callback("Enviando vídeo para o Google Gemini...")
        try:
            video_file = genai.upload_file(path=video_path)
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            if video_file.state.name == "FAILED": raise Exception("Falha no Google.")
            
            if status_callback: status_callback("IA analisando (Visão + Audição)...")

            prompt = f"""
            Analise este vídeo de forma MULTIMODAL (Visual + Audio).
            ORDEM DO USUÁRIO: "{user_orders if user_orders else 'Identifique Title Cards (Telas pretas) e cortes lógicos.'}"
            Retorne JSON PURO: [{{ "inicio": "MM:SS", "fim": "MM:SS", "titulo_arquivo": "Titulo" }}]
            """
            
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content([video_file, prompt], request_options={"timeout": 600})
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

# --- CLASSE 2: PROCESSADOR DE TEMPLATES (CORRIGIDA) ---
class TemplateProcessor:
    def __init__(self):
        pass

    def get_preview_frame(self, video_path, template_path, y_offset):
        """
        Gera preview redimensionando o VÍDEO para caber no TEMPLATE.
        """
        try:
            # 1. Carrega Template (Mestre) e garante transparência
            template_img = Image.open(template_path).convert("RGBA")
            
            # 2. Carrega Frame do Vídeo
            clip = VideoFileClip(video_path)
            # Pega um frame aos 20% do vídeo (evita pegar tela preta de intro)
            frame_t = min(clip.duration * 0.2, 5.0) 
            frame_array = clip.get_frame(frame_t)
            clip.close()
            
            video_img = Image.fromarray(frame_array).convert("RGBA")

            # 3. Redimensiona o VÍDEO para ter a mesma LARGURA do Template
            # O Template dita o tamanho final (ex: 1080px de largura)
            ratio = template_img.width / float(video_img.width)
            new_height = int(video_img.height * ratio)
            
            video_img = video_img.resize((template_img.width, new_height), Image.Resampling.LANCZOS)

            # 4. Cria Canvas do tamanho do Template
            canvas = Image.new('RGBA', template_img.size, (0, 0, 0, 0)) # Fundo transparente

            # 5. Cola o Vídeo (considerando o deslocamento Y)
            # Centraliza o vídeo verticalmente por padrão + o ajuste do usuário
            # Se y_offset for 0, o vídeo começa no topo ou meio? Vamos por no topo + offset
            # Ou melhor: Centralizado + Offset
            
            center_y = (template_img.height - video_img.height) // 2
            final_y = center_y + y_offset
            
            canvas.paste(video_img, (0, final_y))

            # 6. Cola o Template por cima (A Mágica)
            # Usa o próprio template como máscara para garantir transparência
            canvas.paste(template_img, (0, 0), template_img)

            return canvas

        except Exception as e:
            print(f"Erro Preview: {e}")
            return None

    def render_video_with_template(self, video_path, template_path, y_offset, progress_callback=None):
        try:
            clip = VideoFileClip(video_path)
            template = ImageClip(template_path).convert("RGBA") # Garante alpha channel
            
            # 1. Redimensiona o VÍDEO para caber na largura do TEMPLATE
            # (Lógica inversa do MoviePy padrão, aqui o Template manda)
            ratio = template.w / clip.w
            clip_resized = clip.resize(ratio)
            
            # 2. Configura Duração
            template = template.set_duration(clip.duration)
            
            # 3. Posicionamento
            # Calcula o centro vertical
            center_y = (template.h - clip_resized.h) / 2
            final_y = center_y + y_offset
            
            clip_positioned = clip_resized.set_position(("center", final_y))
            template_positioned = template.set_position("center")
            
            # 4. Composição: Vídeo atrás, Template na frente
            final = CompositeVideoClip(
                [clip_positioned, template_positioned], 
                size=template.size
            )
            
            output_path = f"final_render_{int(time.time())}.mp4"
            
            if progress_callback: progress_callback(0.1, "Renderizando (pode demorar)...")
            
            final.write_videofile(
                output_path, 
                codec="libx264", 
                audio_codec="aac", 
                preset="ultrafast", 
                logger=None,
                threads=4
            )
            
            clip.close()
            template.close()
            final.close()
            return output_path
            
        except Exception as e:
            print(f"Erro Render: {e}")
            return None
