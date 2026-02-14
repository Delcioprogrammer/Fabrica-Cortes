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
        download_folder = "downloads_yt"
        if not os.path.exists(download_folder): os.makedirs(download_folder)
        
        # Limpa anteriores
        files = glob.glob(f"{download_folder}/*")
        for f in files: 
            try: os.remove(f)
            except: pass

        if progress_callback: progress_callback("Conectando ao YouTube...")

        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'{download_folder}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'playlistend': 5,
            'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        }

        downloaded_paths = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if 'entries' in info:
                    for entry in info['entries']:
                        if entry: downloaded_paths.append(ydl.prepare_filename(entry))
                else:
                    downloaded_paths.append(ydl.prepare_filename(info))
            
            # Filtra caminhos inválidos
            downloaded_paths = [p for p in downloaded_paths if p and os.path.exists(p)]
            
            if progress_callback: progress_callback(f"Download concluído! {len(downloaded_paths)} vídeos baixados.")
            return downloaded_paths

        except Exception as e:
            print(f"Erro download: {e}")
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
        if status_callback: status_callback(f"Enviando para o Gemini (Isso pode demorar)...")
        
        try:
            video_file = genai.upload_file(path=video_path)
            
            # Espera processar
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name == "FAILED":
                print("❌ O Google falhou ao processar o arquivo de vídeo.")
                return []

            if status_callback: status_callback("IA analisando (Filtros de segurança desativados)...")

            prompt = f"""
            ATUE COMO UM EDITOR PROFISSIONAL DE DOCUMENTÁRIOS.
            Analise este vídeo (Visual + Áudio).
            
            ORDEM DO USUÁRIO: "{user_orders}"
            
            SE A ORDEM FOR VAZIA, SIGA ESTE PADRÃO:
            Identifique visualmente os "Title Cards" (Telas pretas com texto branco) que separam os segmentos.
            INICIO: Quando a tela preta aparece.
            FIM: Imediatamente antes da próxima tela preta.
            
            IMPORTANTE:
            Se o vídeo contiver temas sensíveis (acidentes, true crime), ANALISE MESMO ASSIM. O objetivo é documental e educativo.
            
            Retorne APENAS JSON:
            [
              {{"inicio": "MM:SS", "fim": "MM:SS", "titulo_arquivo": "Titulo"}}
            ]
            """
            
            # --- AQUI ESTÁ A CORREÇÃO: LIBERAR CONTEÚDO SENSÍVEL ---
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(
                [video_file, prompt], 
                safety_settings=safety_settings, # Aplica a regra "sem bloqueios"
                request_options={"timeout": 600}
            )
            
            try:
                return self._clean_json_response(response.text)
            except Exception as e:
                # Se cair aqui, provavelmente foi bloqueado mesmo com BLOCK_NONE ou deu erro de servidor
                print(f"Erro ao ler resposta (pode ser bloqueio de segurança): {e}")
                if hasattr(response, 'prompt_feedback'):
                    print(f"Feedback de Segurança: {response.prompt_feedback}")
                return []

        except Exception as e:
            print(f"Erro geral na IA: {e}")
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
                    # Nome único para evitar sobrescrever se for playlist
                    filename = os.path.join(output_dir, f"Corte_{int(time.time())}_{i}_{safe_title}.mp4")

                    if end > clip.duration: end = clip.duration
                    if end <= start: continue

                    sub = clip.subclip(start, end)
                    if speed_factor != 1.0:
                        sub = sub.fx(vfx.speedx, speed_factor)
                    
                    sub.write_videofile(filename, codec="libx264", audio_codec="aac", preset='ultrafast', logger=None)
                    generated_files.append(filename)
                    
                    if progress_callback: progress_callback((i+1)/len(cuts_data))
                except Exception as e:
                    print(f"Erro ao cortar trecho {i}: {e}")
            
            clip.close()
            return generated_files
        except Exception as e:
            print(f"Erro ao abrir vídeo para cortes: {e}")
            return []
