import os
import time
import json
import re
import glob
import yt_dlp
import google.generativeai as genai
from moviepy.editor import VideoFileClip, vfx

class VideoProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=self.api_key)
        self.model_name = 'models/gemini-1.5-flash'

    # --- ATUALIZADO: Agora aceita cookies_path ---
    def download_from_youtube(self, url, cookies_path=None, progress_callback=None):
        download_folder = "downloads_yt"
        if not os.path.exists(download_folder): os.makedirs(download_folder)
        
        # Limpa downloads anteriores
        files = glob.glob(f"{download_folder}/*")
        for f in files: 
            try: os.remove(f)
            except: pass

        if progress_callback: progress_callback("Conectando ao YouTube (Isso pode demorar um pouco)...")

        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'{download_folder}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'playlistend': 5, # Limite de segurança
            'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        }

        # Se o usuário enviou cookies, usa eles!
        if cookies_path:
            ydl_opts['cookiefile'] = cookies_path

        downloaded_paths = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if 'entries' in info: # Playlist
                    for entry in info['entries']:
                        if entry: 
                            filename = ydl.prepare_filename(entry)
                            downloaded_paths.append(filename)
                else: # Vídeo único
                    filename = ydl.prepare_filename(info)
                    downloaded_paths.append(filename)
            
            # Verifica se os arquivos realmente existem no disco
            valid_paths = [p for p in downloaded_paths if p and os.path.exists(p)]
            
            if progress_callback: 
                if not valid_paths:
                    progress_callback("⚠️ O YouTube bloqueou o download. Tente usar Cookies.")
                else:
                    progress_callback(f"✅ Download concluído! {len(valid_paths)} vídeos baixados.")
            
            return valid_paths

        except Exception as e:
            print(f"Erro Crítico no Download: {e}")
            if progress_callback: progress_callback(f"❌ Erro: {str(e)}")
            return []

    def _clean_json_response(self, text):
        try:
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match: return json.loads(match.group(0))
            clean_text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except: return []

    def analyze_video(self, video_path, user_orders="", status_callback=None):
        if status_callback: status_callback(f"Enviando para o Gemini...")
        
        try:
            video_file = genai.upload_file(path=video_path)
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name == "FAILED": return []

            if status_callback: status_callback("IA analisando (Sem filtros de segurança)...")

            prompt = f"""
            ATUE COMO EDITOR DE DOCUMENTÁRIOS.
            Analise este vídeo (Visual + Áudio).
            ORDEM: "{user_orders}"
            SE VAZIO: Identifique cortes por Telas Pretas (Title Cards).
            Retorne APENAS JSON: [{{"inicio": "MM:SS", "fim": "MM:SS", "titulo_arquivo": "Titulo"}}]
            """
            
            # Filtros desligados para permitir conteúdo sensível
            safety = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content([video_file, prompt], safety_settings=safety)
            return self._clean_json_response(response.text)

        except Exception as e:
            print(f"Erro IA: {e}")
            return []

    def _time_to_seconds(self, time_str):
        try:
            p = list(map(int, time_str.split(':')))
            if len(p) == 2: return p[0]*60 + p[1]
            elif len(p) == 3: return p[0]*3600 + p[1]*60 + p[2]
            return 0
        except: return 0

    def process_cuts(self, video_path, cuts_data, speed_factor=1.1, progress_callback=None):
        try:
            clip = VideoFileClip(video_path)
            generated_files = []
            output_dir = "cortes_temp"
            if not os.path.exists(output_dir): os.makedirs(output_dir)

            for i, cut in enumerate(cuts_data):
                try:
                    start = self._time_to_seconds(cut['inicio'])
                    end = self._time_to_seconds(cut['fim'])
                    safe_title = "".join([c for c in cut['titulo_arquivo'] if c.isalnum()]).strip()[:30]
                    filename = os.path.join(output_dir, f"Corte_{int(time.time())}_{i}_{safe_title}.mp4")

                    if end > clip.duration: end = clip.duration
                    if end <= start: continue

                    sub = clip.subclip(start, end).fx(vfx.speedx, speed_factor)
                    sub.write_videofile(filename, codec="libx264", audio_codec="aac", preset='ultrafast', logger=None)
                    generated_files.append(filename)
                    if progress_callback: progress_callback((i+1)/len(cuts_data))
                except: pass
            
            clip.close()
            return generated_files
        except: return []
