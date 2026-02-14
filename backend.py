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

    def download_from_youtube(self, url, progress_callback=None):
        """
        Baixa vídeos do YouTube (Link único ou Playlist).
        Retorna uma lista de caminhos dos arquivos baixados.
        """
        download_folder = "downloads_yt"
        if not os.path.exists(download_folder): os.makedirs(download_folder)
        
        # Limpa downloads antigos para não lotar o disco
        files = glob.glob(f"{download_folder}/*")
        for f in files: 
            try: os.remove(f)
            except: pass

        if progress_callback: progress_callback("Conectando ao YouTube...")

        ydl_opts = {
            'format': 'best[ext=mp4]/best', # Tenta MP4 primeiro
            'outtmpl': f'{download_folder}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True, # Se um vídeo da playlist falhar, continua
            'playlistend': 5,     # LIMITE DE SEGURANÇA: Max 5 vídeos por playlist
            'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        }

        downloaded_paths = []
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Lógica para detectar se é Playlist ou Vídeo Único
                if 'entries' in info:
                    # É Playlist
                    for entry in info['entries']:
                        if entry:
                            filename = ydl.prepare_filename(entry)
                            downloaded_paths.append(filename)
                else:
                    # É Vídeo Único
                    filename = ydl.prepare_filename(info)
                    downloaded_paths.append(filename)
                    
            if progress_callback: progress_callback(f"Download concluído! {len(downloaded_paths)} vídeos baixados.")
            return downloaded_paths

        except Exception as e:
            print(f"Erro no download: {e}")
            return []

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

    def analyze_video(self, video_path, user_orders="", status_callback=None):
        # Renomeei de 'upload_and_analyze' para 'analyze_video' para ficar mais limpo
        if status_callback: status_callback(f"Enviando {os.path.basename(video_path)} para o Gemini...")
        
        try:
            video_file = genai.upload_file(path=video_path)
            
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name == "FAILED": return []

            if status_callback: status_callback("IA analisando (Visão + Audição)...")

            prompt = f"""
            Analise este vídeo de forma MULTIMODAL (Visão + Audição).
            
            ORDEM DO USUÁRIO: "{user_orders}"
            
            Se a ordem for vazia, use o padrão: Identifique segmentos separados por Telas Pretas (Title Cards).
            
            Retorne APENAS JSON puro:
            [
              {{"inicio": "MM:SS", "fim": "MM:SS", "titulo_arquivo": "Titulo"}}
            ]
            """
            
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content([video_file, prompt])
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
        clip = VideoFileClip(video_path)
        generated_files = []
        output_dir = "cortes_temp"
        if not os.path.exists(output_dir): os.makedirs(output_dir)

        for i, cut in enumerate(cuts_data):
            try:
                start = self._time_to_seconds(cut['inicio'])
                end = self._time_to_seconds(cut['fim'])
                safe_title = "".join([c for c in cut['titulo_arquivo'] if c.isalnum()]).strip()[:30]
                filename = os.path.join(output_dir, f"{os.path.basename(video_path)[:10]}_{i}_{safe_title}.mp4")

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
