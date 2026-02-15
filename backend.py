import os
import time
import json
import re
import google.generativeai as genai
from moviepy.editor import VideoFileClip, CompositeVideoClip, vfx, VideoClip
from PIL import Image, ImageOps
import numpy as np

# --- CLASSE 1: PROCESSADOR DE CORTES (IA) ---
# (Mantida idêntica para não quebrar o que já funciona)
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
        Gera preview usando composição ALPHA precisa.
        """
        clip_main = None
        clip_tpl = None
        try:
            # 1. Carrega Frame do Vídeo Principal (Fundo)
            clip_main = VideoFileClip(video_path)
            t_main = min(clip_main.duration * 0.2, 2.0)
            frame_main = clip_main.get_frame(t_main)
            img_main = Image.fromarray(frame_main).convert("RGBA")

            # 2. Carrega Frame do Template (Frente)
            clip_tpl = VideoFileClip(template_path)
            frame_tpl = clip_tpl.get_frame(0) # Pega o primeiro frame
            img_tpl = Image.fromarray(frame_tpl).convert("RGBA")

            # 3. Redimensiona Fundo para a largura da Frente
            target_width = img_tpl.width
            ratio = target_width / float(img_main.width)
            target_height = int(img_main.height * ratio)
            img_main = img_main.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # 4. Cria Canvas Transparente do tamanho do Template
            canvas = Image.new('RGBA', img_tpl.size, (0, 0, 0, 0))

            # 5. Posiciona o Fundo (Vídeo)
            # Centraliza horizontalmente e aplica offset vertical
            center_x = (img_tpl.width - img_main.width) // 2
            center_y = (img_tpl.height - img_main.height) // 2
            final_y = center_y + y_offset
            
            # Cola o vídeo no canvas
            canvas.paste(img_main, (center_x, final_y))

            # 6. Composição Alpha (A Mágica)
            # Usa alpha_composite para garantir que a transparência do template funcione
            final_comp = Image.alpha_composite(canvas, img_tpl)

            return final_comp

        except Exception as e:
            print(f"Erro Preview: {e}")
            return None
        finally:
            # Garante limpeza da memória
            if clip_main: clip_main.close()
            if clip_tpl: clip_tpl.close()

    def render_video_with_template(self, video_path, template_path, y_offset, progress_callback=None):
        """
        Renderiza o vídeo final garantindo fechamento de arquivos.
        """
        clip = None
        template = None
        final = None
        
        try:
            # Carrega arquivos
            clip = VideoFileClip(video_path)
            # has_mask=True é essencial para vídeos transparentes (MOV/WEBM)
            template = VideoFileClip(template_path, has_mask=True) 

            # 1. Ajuste de Tamanho (Template é o mestre)
            ratio = template.w / clip.w
            clip_resized = clip.resize(ratio)

            # 2. Loop do Template
            # Se o vídeo for maior que o template, o template repete
            if clip.duration > template.duration:
                template_loop = vfx.loop(template, duration=clip.duration)
            else:
                template_loop = template.set_duration(clip.duration)

            # 3. Posicionamento
            center_y = (template.h - clip_resized.h) / 2
            final_y = center_y + y_offset
            
            clip_pos = clip_resized.set_position(("center", final_y))
            template_pos = template_loop.set_position("center")

            # 4. Renderização
            final = CompositeVideoClip([clip_pos, template_pos], size=template.size)
            final = final.set_audio(clip.audio)

            output_path = f"final_render_{int(time.time())}.mp4"

            if progress_callback: progress_callback(0.3, "Renderizando pixels...")

            final.write_videofile(
                output_path, 
                codec="libx264", 
                audio_codec="aac", 
                preset="ultrafast",
                threads=4,
                logger=None
            )
            
            return output_path

        except Exception as e:
            print(f"Erro Render: {e}")
            return None
        finally:
            # LIMPEZA CRÍTICA: Fecha os arquivos para o Windows/Linux liberar o download
            if clip: clip.close()
            if template: template.close()
            if final: final.close()
