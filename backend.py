import os
import time
import json
import re
import glob
import logging
import uuid
import shutil
import yt_dlp
import google.generativeai as genai
from moviepy.editor import VideoFileClip, vfx

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=self.api_key)
        self.model_name = 'models/gemini-1.5-flash'
        for folder in ["downloads_yt", "cortes_temp"]:
            os.makedirs(folder, exist_ok=True)

    def optimize_prompt(self, raw_text):
        if not raw_text or len(raw_text) < 3: return raw_text
        try:
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(f"Melhore este prompt para edição de vídeo IA: {raw_text}")
            return response.text.strip()
        except: return raw_text

    def _cleanup_old_files(self, folder):
        try:
            for f in glob.glob(f"{folder}/*"):
                try: os.remove(f)
                except: pass
        except: pass

    def download_from_youtube(self, url, cookies_path=None, progress_callback=None):
        self._cleanup_old_files("downloads_yt")
        session_id = str(uuid.uuid4())[:8]
        
        if progress_callback: progress_callback("🚀 Conectando ao YouTube...")

        # CONFIGURAÇÃO ANTI-BLOQUEIO
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'downloads_yt/{session_id}_%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'playlistend': 3,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        }

        # AQUI O CÓDIGO USA SEUS COOKIES
        if cookies_path:
            ydl_opts['cookiefile'] = cookies_path
            if progress_callback: progress_callback("🍪 Cookies detectados! Usando autenticação...")

        downloaded_paths = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=True)
                except Exception as e:
                    if "Sign in" in str(e): raise Exception("ERRO CRÍTICO: O YouTube pediu login. O arquivo cookies.txt é OBRIGATÓRIO aqui.")
                    raise e

                entries = info['entries'] if 'entries' in info else [info]
                for entry in entries:
                    if entry:
                        filename = ydl.prepare_filename(entry)
                        if not os.path.exists(filename):
                            base = os.path.splitext(filename)[0]
                            found = glob.glob(f"{base}*")
                            if found: filename = found[0]
                        if os.path.exists(filename): downloaded_paths.append(filename)

            valid_paths = [p for p in downloaded_paths if os.path.getsize(p) > 0]
            if not valid_paths: raise Exception("O YouTube bloqueou o IP do servidor.")
            return valid_paths

        except Exception as e:
            logger.error(f"Erro Download: {e}")
            if progress_callback: progress_callback(f"❌ Erro: {str(e)}")
            return []

    def _clean_json_response(self, text):
        try:
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match: return json.loads(match.group(0))
            return json.loads(text.replace("```json", "").replace("```", "").strip())
        except: return []

    def analyze_video(self, video_path, user_orders="", status_callback=None):
        try:
            video_file = genai.upload_file(path=video_path)
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            
            if video_file.state.name == "FAILED": return []

            prompt = f"""
            ATUE COMO EDITOR DE VÍDEO.
            Analise visualmente e auditivamente.
            PEDIDO: "{user_orders}"
            Se vazio, corte por Telas Pretas (Title Cards).
            Retorne JSON: [{{"inicio": "MM:SS", "fim": "MM:SS", "titulo_arquivo": "nome"}}]
            """
            
            safety = [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
            model = genai.GenerativeModel(self.model_name)
            res = model.generate_content([video_file, prompt], safety_settings=safety)
            return self._clean_json_response(res.text)
        except: return []

    def _time_to_seconds(self, t):
        try:
            p = list(map(int, t.split(':')))
            if len(p)==2: return p[0]*60+p[1]
            return p[0]*3600+p[1]*60+p[2]
        except: return 0

    def process_cuts(self, video_path, cuts_data, speed_factor=1.1, progress_callback=None):
        try:
            clip = VideoFileClip(video_path)
            files = []
            
            for i, cut in enumerate(cuts_data):
                try:
                    s = self._time_to_seconds(cut['inicio'])
                    e = self._time_to_seconds(cut['fim'])
                    if e <= s: continue
                    
                    # SEM CROP (Mantém original)
                    sub = clip.subclip(s, e)
                    
                    if speed_factor != 1.0:
                        sub = sub.fx(vfx.speedx, speed_factor)
                    
                    safe_name = "".join([c for c in cut['titulo_arquivo'] if c.isalnum()]).strip()[:20]
                    name = f"cortes_temp/{uuid.uuid4().hex[:6]}_{safe_name}.mp4"
                    
                    sub.write_videofile(name, codec="libx264", audio_codec="aac", preset="ultrafast", logger=None)
                    files.append(name)
                except: pass

            clip.close()
            return files
        except: return []

import os
import time
import json
import re
import google.generativeai as genai
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, vfx
import numpy as np
from PIL import Image

# ... (Mantenha a classe VideoProcessor antiga aqui em cima) ...

class TemplateProcessor:
    """
    Classe responsável por aplicar Templates (Overlays) em vídeos.
    """
    def __init__(self):
        pass

    def get_preview_frame(self, video_path, template_path, y_offset):
        """
        Gera uma IMAGEM estática de como o vídeo vai ficar com o template.
        Isso é ultra-rápido para o usuário ajustar a posição sem travar.
        """
        try:
            # 1. Carrega o vídeo e pega um frame do meio (para ter imagem)
            clip = VideoFileClip(video_path)
            frame_t = clip.duration / 2  # Pega frame do meio
            video_frame = clip.get_frame(frame_t) # Numpy Array
            
            # 2. Carrega o Template (Imagem)
            template_clip = ImageClip(template_path)
            
            # Ajusta tamanho do template para bater com a largura do vídeo
            if template_clip.w != clip.w:
                template_clip = template_clip.resize(width=clip.w)

            # 3. Cria a composição (apenas para este frame)
            # O vídeo é o fundo, movido pelo y_offset
            # O template fica por cima (fixo ou ajustado)
            
            # Nota: No MoviePy, a ordem na lista define as camadas (último fica em cima)
            # Vamos criar um clipe de imagem a partir do frame do vídeo
            frame_clip = ImageClip(video_frame).set_position(("center", y_offset))
            
            # Compõe: Fundo (Vídeo deslocado) + Frente (Template)
            final_comp = CompositeVideoClip([frame_clip, template_clip.set_position("center")], size=template_clip.size)
            
            # Gera o frame final
            preview_image = final_comp.get_frame(0)
            
            # Limpeza
            clip.close()
            template_clip.close()
            final_comp.close()
            
            return preview_image
            
        except Exception as e:
            print(f"Erro no preview: {e}")
            return None

    def render_video_with_template(self, video_path, template_path, y_offset, progress_callback=None):
        """
        Renderiza o VÍDEO COMPLETO com o template aplicado.
        """
        try:
            clip = VideoFileClip(video_path)
            template = ImageClip(template_path).set_duration(clip.duration)
            
            # Ajusta largura do template
            if template.w != clip.w:
                template = template.resize(width=clip.w)
            
            # Posiciona o vídeo (Fundo)
            # ("center", y_offset) -> Centralizado horizontalmente, deslocado verticalmente
            clip_positioned = clip.set_position(("center", y_offset))
            template_positioned = template.set_position("center")
            
            # Composição: Vídeo atrás, Template na frente
            final = CompositeVideoClip([clip_positioned, template_positioned], size=template.size)
            
            output_path = f"template_output_{int(time.time())}.mp4"
            
            # Callback para barra de progresso (simulado, pois moviepy trava o processo)
            if progress_callback: progress_callback(0.5, "Renderizando vídeo final...")
            
            final.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                logger=None
            )
            
            clip.close()
            template.close()
            final.close()
            
            return output_path
            
        except Exception as e:
            print(f"Erro ao renderizar template: {e}")
            return None
