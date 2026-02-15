import os
import time
import json
import re
import google.generativeai as genai
from moviepy.editor import VideoFileClip, CompositeVideoClip, vfx
from PIL import Image
import numpy as np

# --- CLASSE 1: PROCESSADOR DE CORTES (SEM ALTERAÇÕES) ---
class VideoProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        genai.configure(api_key=self.api_key)
        self.model_name = 'models/gemini-1.5-flash'

    def _clean_json_response(self, text):
        try:
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match: return json.loads(match.group(0))
            else: return json.loads(text.replace("```json", "").replace("```", "").strip())
        except: return []

    def upload_and_analyze(self, video_path, user_orders="", status_callback=None):
        if status_callback: status_callback("Enviando vídeo para o Gemini...")
        try:
            video_file = genai.upload_file(path=video_path)
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            if video_file.state.name == "FAILED": raise Exception("Falha no Google.")
            
            if status_callback: status_callback("IA analisando (Visão + Audição)...")
            prompt = f"""
            Analise MULTIMODAL (Visual+Audio). ORDEM: "{user_orders if user_orders else 'Cortes virais'}"
            JSON PURO: [{{ "inicio": "MM:SS", "fim": "MM:SS", "titulo_arquivo": "Titulo" }}]
            """
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content([video_file, prompt])
            return self._clean_json_response(response.text)
        except Exception as e:
            print(f"Erro: {e}"); return []

    def _time_to_seconds(self, t):
        try:
            p = list(map(int, t.split(':')))
            if len(p)==2: return p[0]*60+p[1]
            elif len(p)==3: return p[0]*3600+p[1]*60+p[2]
            return 0
        except: return 0

    def process_cuts(self, video_path, cuts_data, speed_factor=1.1, progress_callback=None):
        clip = VideoFileClip(video_path)
        files = []
        out_dir = "cortes_temp"
        if not os.path.exists(out_dir): os.makedirs(out_dir)
        for i, c in enumerate(cuts_data):
            try:
                s, e = self._time_to_seconds(c['inicio']), self._time_to_seconds(c['fim'])
                name = f"{out_dir}/Corte_{i+1}.mp4"
                if e > clip.duration: e = clip.duration
                if e <= s: continue
                sub = clip.subclip(s, e)
                if speed_factor != 1.0: sub = sub.fx(vfx.speedx, speed_factor)
                sub.write_videofile(name, codec="libx264", audio_codec="aac", preset='ultrafast', logger=None)
                files.append(name)
                if progress_callback: progress_callback((i+1)/len(cuts_data))
            except: pass
        clip.close()
        return files

# --- CLASSE 2: PROCESSADOR DE TEMPLATES (VÍDEO + VÍDEO) ---
class TemplateProcessor:
    def __init__(self):
        pass

    def get_preview_frame(self, video_path, template_path, y_offset):
        """
        Gera preview pegando um frame do VÍDEO e um frame do TEMPLATE (Vídeo).
        """
        try:
            # 1. Carrega Vídeo Principal
            clip_main = VideoFileClip(video_path)
            t_main = min(clip_main.duration * 0.2, 3.0) 
            frame_main = clip_main.get_frame(t_main)
            clip_main.close()
            img_main = Image.fromarray(frame_main).convert("RGBA")

            # 2. Carrega Template (Agora é um VÍDEO)
            clip_tpl = VideoFileClip(template_path)
            # Pega um frame do template (se for loop, qualquer frame serve)
            frame_tpl = clip_tpl.get_frame(0.5) 
            clip_tpl.close()
            img_tpl = Image.fromarray(frame_tpl).convert("RGBA")

            # 3. Lógica de Redimensionamento (Template manda no tamanho)
            ratio = img_tpl.width / float(img_main.width)
            new_h = int(img_main.height * ratio)
            img_main = img_main.resize((img_tpl.width, new_h), Image.Resampling.LANCZOS)

            # 4. Canvas e Colagem
            canvas = Image.new('RGBA', img_tpl.size, (0,0,0,0))
            
            # Centraliza Main verticalmente + Offset
            center_y = (img_tpl.height - img_main.height) // 2
            final_y = center_y + y_offset
            
            canvas.paste(img_main, (0, final_y))
            # Cola o frame do template por cima
            canvas.paste(img_tpl, (0,0), img_tpl) # Usa o próprio frame como máscara

            return canvas
        except Exception as e:
            print(f"Erro Preview: {e}")
            return None

    def render_video_with_template(self, video_path, template_path, y_offset, progress_callback=None):
        try:
            clip = VideoFileClip(video_path)
            # Carrega o template como VÍDEO agora, garantindo canal Alpha (transparência)
            template = VideoFileClip(template_path, has_mask=True)
            
            # 1. Ajusta tamanho do Vídeo Principal
            ratio = template.w / clip.w
            clip_resized = clip.resize(ratio)
            
            # 2. Lógica de LOOP: O template deve durar o mesmo que o vídeo principal
            # Se o template for curto (ex: 10s) e o vídeo longo (60s), o template repete.
            template_loop = vfx.loop(template, duration=clip.duration)
            
            # 3. Posicionamento
            center_y = (template.h - clip_resized.h) / 2
            final_y = center_y + y_offset
            
            clip_pos = clip_resized.set_position(("center", final_y))
            template_pos = template_loop.set_position("center")
            
            # 4. Composição
            final = CompositeVideoClip([clip_pos, template_pos], size=template.size)
            # Mantém o áudio do vídeo original
            final = final.set_audio(clip.audio) 
            
            out_path = f"final_{int(time.time())}.mp4"
            if progress_callback: progress_callback(0.2, "Renderizando (Isso demora um pouco)...")
            
            final.write_videofile(out_path, codec="libx264", audio_codec="aac", preset="ultrafast", logger=None, threads=4)
            
            clip.close()
            template.close()
            final.close()
            return out_path
        except Exception as e:
            print(f"Erro Render: {e}")
            return None
