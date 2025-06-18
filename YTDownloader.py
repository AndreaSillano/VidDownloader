import flet as ft
from pytubefix import YouTube
import ssl
import threading
import requests
from io import BytesIO
import os
import queue
import subprocess
import time

from flet import Icons, Icon
ssl._create_default_https_context = ssl._create_unverified_context

FFMPEG_BIN = os.path.join(os.path.dirname(__file__), 'resources/ffmpeg')
FFPROBE_BIN = os.path.join(os.path.dirname(__file__), 'resources/ffprobe')

class VidDownloaderApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "VidDownloader"
        self.page.window.width = 520
        self.page.window.height = 750
        self.page.window.resizable = False
        self.center_window()

        self.cancel_flag = threading.Event()
        self.download_thread = None
        self.download_only_audio_thread = None
        self.worker_thread = None

        self.setup_ui()

    def center_window(self):
        self.page.window.center()

    def setup_ui(self):
        # Video/Audio selection radio buttons
        self.video_audio_var = ft.RadioGroup(content=ft.Row([
            ft.Radio(value="Video", label="Video with audio"),
            ft.Radio(value="Audio", label="Audio only")
        ]), value="Video", on_change=self.on_video_audio_change)
        self.title = ft.Text("VidDownloader", size=30, weight='bold')
        # URL input
        self.link_icon = ft.Icon(Icons.LINK)
        self.url_label = ft.Text("Youtube Url:")
        self.url_entry = ft.TextField(label="YouTube URL", width=350, expand=True)
        self.fetch_info_button = ft.ElevatedButton(
            icon=Icons.REFRESH,
            text="Fetch Info",
            width=150,
            height=50,
            on_click=self.fetch_video_info
        )
        self.input_url = ft.Column([ft.Row([self.link_icon,self.url_label]),
                                    ft.Row([
                                    self.url_entry,
                                    self.fetch_info_button
                                    ])
                                   ])


        # Info display area
        self.thumbnail_image = ft.Image(width=160, height=90, visible=False)
        self.video_name_label = ft.Text("N/A", weight=ft.FontWeight.W_600)
        # Views
        self.views_icon = Icon(Icons.REMOVE_RED_EYE_OUTLINED)
        self.views_label = ft.Text("N/A")
        self.views_row =ft.Row([self.views_icon,self.views_label])
        # Duration
        self.duration_label = ft.Text("N/A")
        self.duration_icon = Icon(Icons.HOURGLASS_BOTTOM_ROUNDED)
        self.duration_row = ft.Row([self.duration_icon, self.duration_label])
        # Author
        self.author_icon = Icon(Icons.PERSON)
        self.author_label = ft.Text("N/A")
        self.author_row = ft.Row([self.author_icon, self.author_label])
        #Date
        self.pub_date_label = ft.Text("N/A")
        self.pub_date_label_icon = Icon(Icons.CALENDAR_MONTH_OUTLINED)
        self.calendar_row = ft.Row([self.pub_date_label_icon,self.pub_date_label])
        self.infos = ft.Row([self.thumbnail_image,ft.Column([
                    self.video_name_label,
                    ft.Column([
                        ft.Row([ self.author_row,
                    self.views_row],alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                    self.duration_row,
                    self.calendar_row],alignment=ft.MainAxisAlignment.SPACE_BETWEEN)])
                ])],alignment=ft.MainAxisAlignment.CENTER,visible=False)
        self.fetch_loading = ft.Row([ft.Column([ft.ProgressRing(width=32, height=32, stroke_width = 5), ft.Text("Fetching Info")],horizontal_alignment=ft.CrossAxisAlignment.CENTER)],alignment=ft.MainAxisAlignment.CENTER, visible=True)
        self.info_column =ft.Container(ft.Column(
            [
                self.fetch_loading,
                self.infos

            ],
       alignment=ft.MainAxisAlignment.CENTER ), bgcolor=ft.Colors.GREY_200, expand=True, height=150, border_radius=10,  visible=False)

        # Resolution dropdown
        # Audio checkbox
        self.resolution_icons = Icon(Icons.LOCAL_MOVIES_OUTLINED)
        self.audio_icon = Icon(Icons.MUSIC_NOTE_ROUNDED)
        self.add_audio_checkbox = ft.Checkbox(
        label="with Audio",
        value=True,
        disabled=False,
        on_change=self.on_audio_checkbox_change
        )
        self.with_audio = ft.Row([self.audio_icon, self.add_audio_checkbox])


        self.resolution_label = ft.Text("Resolution")
        self.resultion_top = ft.Row([self.resolution_icons, self.resolution_label])
        self.resolution_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option("Select a resolution")],
            disabled=True,
            on_change=self.on_resolution_selected,
            expand=True,
            width=510
        )


        self.resultion = ft.Column([
            self.resultion_top,
            self.resolution_dropdown,
            self.with_audio
        ])


        # Folder selection
        self.folder_icon =Icon(Icons.FOLDER_OPEN_ROUNDED)
        self.folder_label = ft.Text("Download Folder")
        self.folder_title = ft.Row([self.folder_icon,self.folder_label])
        self.folder_entry = ft.TextField(width=350, expand=True, disabled=True)
        self.folder_button = ft.ElevatedButton(
            text="Browse",
            on_click=self.browse_folder,
            disabled=True,
            width=150,
            height=50,
        )
        self.folder_row = ft.Column([self.folder_title,ft.Row([self.folder_entry, self.folder_button])])

        # Download button
        self.pb_headline = ft.Text("Downloading...", size=10, visible=False)
        self.pb= ft.ProgressBar(width=400, height=30, border_radius=10, value=0, visible=False)
        self.download_button = ft.ElevatedButton(
            text="Download",
            on_click=self.toggle_download,
            height=50,
            disabled=True,
            expand=True
        )
        self.download_pb = ft.Row([self.pb, self.download_button],alignment=ft.MainAxisAlignment.CENTER, expand=True)
        self.last_row = ft.Column([self.pb_headline, self.download_pb], alignment=ft.MainAxisAlignment.CENTER, expand=True)
        self.download_row =  ft.Container(self.last_row, margin=ft.margin.only(top=10, bottom=30), visible=False)

        # Console area
        self.console_text = ft.Column(
            [ft.Text("Console", weight=ft.FontWeight.BOLD)],
            scroll=ft.ScrollMode.ALWAYS,
            height=150,
            width=510,
            expand=True
        )
        self.badge_text = ft.Text("Error")
        self.dlg = ft.SnackBar(self.badge_text, bgcolor=ft.Colors.GREEN_300)


        # Layout
        self.page.add(
            ft.Column([
                ft.Row([ self.title ], alignment=ft.MainAxisAlignment.CENTER),
                self.video_audio_var,
                self.input_url,
                self.info_column,
                self.resultion,
                self.folder_row,
                self.last_row,
                ft.Container(
                    content=self.console_text,
                    border=ft.border.all(1, ft.colors.GREY_400),
                    padding=5,
                    border_radius=5,
                    visible=False
                )
            ], expand=True, scroll=ft.ScrollMode.HIDDEN,)
        )

    def truncate_text(self, text, max_length=37):
        if len(text) > max_length:
            return text[:max_length-3] + "..."
        return text

    def browse_folder(self, e):
        def get_directory_result(result: ft.FilePickerResultEvent):
            if result.path:
                self.folder_entry.value = result.path
                self.append_to_console(f"Download folder set to {result.path}")
                self.download_button.disabled = False
                self.page.update()

        file_picker = ft.FilePicker(on_result=get_directory_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.get_directory_path()
    def toogle_badge(self,msg, error=False):
        if not error:
            self.dlg.bgcolor = ft.Colors.GREEN_300
        else:
            self.dlg.bgcolor = ft.Colors.RED_300
        self.badge_text.value = msg
        self.page.open(self.dlg)
        #self.page.update()
    def fetch_video_info(self, e):
        url = self.url_entry.value

        if not url:
            self.toogle_badge("Please enter a YouTube URL.", True)
            self.append_to_console("Error: Please enter a YouTube URL.", error=True)
            return

        try:
            self.append_to_console("Fetching video information. Please wait...")

            yt = YouTube(url)
            self.info_column.visible = True
            self.infos.visible = False
            self.fetch_loading.visible = True
            self.page.update()
            #print(yt.author, yt.views, yt.publish_date)
            # Display the video thumbnail
            self.pub_date_label.value = yt.publish_date.date()
            self.views_label.value = yt.views
            self.author_label.value = yt.author
            img_url = yt.thumbnail_url
            response = requests.get(img_url)
            img_data = BytesIO(response.content)

            self.thumbnail_image.src_base64 = self.image_to_base64(img_data)
            self.thumbnail_image.visible = True

            # Display video info
            video_name = self.truncate_text(yt.title)
            self.video_name_label.value = f"{video_name}"

            video_duration = yt.length
            minutes, seconds = divmod(video_duration, 60)
            self.duration_label.value = f"{minutes:02}:{seconds:02}"

            # Fetch streams based on video/audio selection
            if self.video_audio_var.value == "Video":
                streams = yt.streams.order_by('resolution').filter(only_video=True)
                stream_size = streams[0].filesize
                #size_text = f"{stream_size // (1024 * 1024)} MB" if stream_size >= 1024 * 1024 else f"{stream_size // 1024} KB"
                #self.views_label.value = f"{yt.views}"

                resolutions = []
                for stream in streams:
                    if stream.resolution:
                        if stream.mime_type == "video/webm":
                            res = f"{stream.resolution} (WebM - Conversion Needed)"
                            if res not in resolutions:
                                resolutions.append(f"{stream.resolution} (WebM - Conversion Needed)")
                        else:
                            if stream.resolution not in resolutions:
                                resolutions.append(stream.resolution)

                if resolutions:
                    self.resolution_dropdown.options = [ft.dropdown.Option(res) for res in resolutions]
                    self.resolution_dropdown.value = resolutions[-1]
                    self.resolution_dropdown.disabled = False
                    self.append_to_console("Resolutions fetched! Select one to proceed.")
                else:
                    self.toogle_badge("No streams found for this URL.", True)
                    self.append_to_console("Error: No streams found for this URL.", error=True)
            else:
                streams = yt.streams.filter(only_audio=True).order_by('abr')
                stream_size = streams[0].filesize
                #size_text = f"{stream_size // (1024 * 1024)} MB" if stream_size >= 1024 * 1024 else f"{stream_size // 1024} KB"
                #self.size_label.value = f"{size_text}"

                audio_bitrates = []
                for stream in streams:
                    if stream.abr:
                        if stream.mime_type == "audio/webm":
                            audio_bitrates.append(f"{stream.abr} (WebM - Conversion Needed)")
                        else:
                            audio_bitrates.append(stream.abr)

                if audio_bitrates:
                    self.resolution_dropdown.options = [ft.dropdown.Option(bitrate) for bitrate in audio_bitrates]
                    self.resolution_dropdown.value = audio_bitrates[-1]
                    self.resolution_dropdown.disabled = False
                    self.append_to_console("Audio bitrates fetched! Select one to proceed.")
                else:
                    self.toogle_badge("No audio streams found for this URL.", True)
                    self.append_to_console("Error: No audio streams found for this URL.", error=True)

            self.fetch_loading.visible = False
            self.infos.visible = True
            self.page.update()

        except Exception as e:
            self.toogle_badge(f"Error: {str(e)}", True)
            self.append_to_console(f"Error: {str(e)}", error=True)

    def image_to_base64(self, img_data):
        from PIL import Image
        import base64
        from io import BytesIO

        img = Image.open(img_data)
        img = img.resize((160, 90), Image.LANCZOS)

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def on_resolution_selected(self, e):
        self.folder_button.disabled = False
        self.append_to_console(f"Resolution set to {self.resolution_dropdown.value}")

    def on_video_audio_change(self, e):
        self.reset_ui()

        if self.video_audio_var.value == 'Audio':
            self.add_audio_checkbox.disabled = True
            self.add_audio_checkbox.value = True
        else:
            self.add_audio_checkbox.disabled = False
            self.add_audio_checkbox.value = False
        self.page.update()

    def on_audio_checkbox_change(self, e):
        pass  # No special handling needed for checkbox change

    def reset_ui(self):
        self.url_entry.value = ""
        self.folder_entry.value = ""
        self.author_label.value = "N/A"
        self.download_button.text = "Download"
        self.thumbnail_image.visible = False
        self.pb.visible = False
        self.pb_headline.visible = False
        self.views_label.value = "N/A"
        self.pub_date_label.value = "N/A"
        self.duration_label.value = "N/A"
        self.resolution_dropdown.value = None
        self.resolution_dropdown.options = []
        self.resolution_dropdown.disabled = True
        self.pb.value = 0
        self.pb_headline.value = "Downloading..."

        if self.video_audio_var.value != "Video":
            self.folder_button.disabled = False
            self.add_audio_checkbox.disabled = True
        else:
            self.folder_button.disabled = True
            self.add_audio_checkbox.disabled = False

        self.download_button.disabled = True
        self.info_column.visible = False
        self.page.update()

    def get_unique_filename(self, filepath):
        if not os.path.exists(filepath):
            return filepath

        base, ext = os.path.splitext(filepath)
        counter = 1
        new_filepath = f"{base}_{counter}{ext}"

        while os.path.exists(new_filepath):
            counter += 1
            new_filepath = f"{base}_{counter}{ext}"

        return new_filepath

    def delete_files_in_folder(self):
        current_folder = os.getcwd()
        folder_path = os.path.join(current_folder, "tmp")
        if os.path.exists(folder_path):
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
    def disable_ui(self):
        self.download_button.text = "Cancel"
        self.video_audio_var.disabled = True
        self.folder_button.disabled = True
        self.fetch_info_button.disabled = True
        self.resolution_dropdown.disabled = True
        self.url_entry.disabled = True
        self.folder_entry.disabled = True
        self.add_audio_checkbox.disabled = True
        self.page.update()
    def toggle_download(self, e):
        if self.download_button.text == "Download":
            current_folder = os.getcwd()
            self.pb.visible = True
            self.pb_headline.visible = True
            self.page.update()
            tmp_folder = os.path.join(current_folder, "tmp")
            if not os.path.exists(tmp_folder):
                os.makedirs(tmp_folder)
            else:
                self.delete_files_in_folder()


            self.cancel_flag.clear()

            if self.video_audio_var.value == "Video":
                self.disable_ui()

                self.download_thread = threading.Thread(target=self.download_video)
                self.download_thread.start()

                if self.add_audio_checkbox.value:
                    if os.path.exists(FFMPEG_BIN) and os.path.exists(FFPROBE_BIN):
                        self.download_only_audio_thread = threading.Thread(target=self.download_audio)
                        self.download_only_audio_thread.start()
                        self.worker_thread = threading.Thread(target=self.wait_for_download_completion)
                        self.worker_thread.start()
                    else:
                        self.append_to_console("Missing FFMPEG-FFPROBE. Cannot merge audio - Downloading Video", error=True)
                        self.toogle_badge("Missing FFMPEG-FFPROBE. Cannot merge audio", True)
                        self.add_audio_checkbox.value = False
            else:
                self.download_thread = threading.Thread(target=self.download_audio)
                self.download_thread.start()

        else:
            self.cancel_flag.set()
            self.pb.visible = False
            self.pb_headline.visible = False
            self.toogle_badge("Process stopped!", error=True)
            self.page.update()

            if self.download_thread and self.download_thread.is_alive():
                self.download_thread.join(timeout=5)
            if self.download_only_audio_thread and self.download_only_audio_thread.is_alive():
                self.download_only_audio_thread.join(timeout=5)
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=5)

            self.download_button.disabled = False
            self.folder_button.disabled = False
            self.fetch_info_button.disabled = False
            self.resolution_dropdown.disabled = False
            self.url_entry.disabled = False
            self.folder_entry.disabled = False
            self.add_audio_checkbox.disabled = False
            self.pb.visible = False
            self.pb_headline.visible = False

            self.page.update()

        self.page.update()
    def wait_for_download_completion(self):
        if self.download_thread:
            self.download_thread.join()

        if self.download_only_audio_thread:
            self.download_only_audio_thread.join()

        if self.add_audio_checkbox.value:
            try:
                self.merge_video_audio(folder_path=self.folder_entry.value)
                self.append_to_console("Download complete!")
                self.toogle_badge("Download Completed!")

                self.pb.visible = False
                self.pb_headline.visible = False
                self.download_button.disabled = False
                self.download_button.text = "Download"
                self.video_audio_var.disabled = False
                self.folder_button.disabled = False
                self.fetch_info_button.disabled = False
                self.resolution_dropdown.disabled = False
                self.url_entry.disabled = False
                self.folder_entry.disabled = False
                self.add_audio_checkbox.disabled = False
                self.pb.visible = False
                self.pb_headline.visible = False
                self.page.update()
            except Exception as e:
                self.reset_ui()
                self.download_button.disabled = False
                self.toogle_badge(f"Error: {str(e)}", True)
                self.append_to_console(f"Error: {str(e)}", error=True)

    def download_audio(self):
        url = self.url_entry.value
        abr = self.resolution_dropdown.value.split()[0] if self.video_audio_var.value != "Video" else None
        folder_path = self.folder_entry.value
        if self.add_audio_checkbox.value:
            current_folder = os.getcwd()
            tmp_folder = os.path.join(current_folder, "tmp")
            if not os.path.exists(tmp_folder):
                os.makedirs(tmp_folder)
            folder_path = tmp_folder

        if not url:
            self.append_to_console("Error: Please enter a YouTube URL.", error=True)
            self.toogle_badge("Please enter a YouTube URL.", True)
            return

        if not folder_path:
            self.toogle_badge("Please select a download folder.", True)
            self.append_to_console("Error: Please select a download folder.", error=True)
            return

        try:
            yt = YouTube(url, on_progress_callback=self.on_progress_callback if not self.add_audio_checkbox.value else None)

            stream = yt.streams.filter(only_audio=True, abr=abr).order_by('abr').first()
            if abr is not None:
                quality = abr
            else:
                quality = 'tmp'

            if stream:
                self.append_to_console("Downloading audio...")

                file_extension = stream.default_filename.split('.')[-1]
                base_filename = stream.default_filename.replace(f".{file_extension}", "")
                custom_filename = f"{base_filename}_{quality}.{file_extension}"
                if self.video_audio_var.value == 'Video':
                    custom_filename = f"audio_{custom_filename}"
                unique_filename = self.get_unique_filename(custom_filename)
                output_file = stream.download(output_path=folder_path, filename=unique_filename)
                if self.cancel_flag.is_set():
                    self.append_to_console("Download audio stopped.")
                    self.download_button.text = "Download"
                    self.delete_files_in_folder()
                    return

                self.append_to_console("Download audio complete!")

                #self.toogle_badge("Download audio complete!")

                if os.path.exists(FFMPEG_BIN) and os.path.exists(FFPROBE_BIN):
                    if output_file.endswith('.webm') and self.video_audio_var.value != "Video":
                        self.convert_to_mp3_from_webm(output_file, folder_path)
                    elif output_file.endswith('.mp4') and self.video_audio_var.value != "Video":
                        self.convert_to_mp3_from_mp4(output_file, folder_path)
                    elif output_file.endswith('.m4a') and self.video_audio_var.value != "Video":
                        self.convert_to_mp3_from_m4a(output_file, self.folder_entry.value)
                else:
                    self.append_to_console("Missing FFMPEG-FFPROBE. Skipping Conversion", error=True)
                    self.toogle_badge("Missing FFMPEG-FFPROBE. Skipping Conversion", True)
                if self.video_audio_var.value !='Video':
                    self.download_button.text = "Download"
                    self.video_audio_var.disabled = False
                    self.folder_button.disabled = False
                    self.fetch_info_button.disabled = False
                    self.resolution_dropdown.disabled = False
                    self.url_entry.disabled = False
                    self.folder_entry.disabled = False
                    self.pb.visible = False
                    self.pb_headline.visible = False
                    self.toogle_badge("Download Completed!")
            else:
                self.reset_ui()
                self.download_button.disabled = False

        except Exception as e:
            self.reset_ui()
            self.download_button.disabled = False
            self.append_to_console(f"Error: {str(e)}", error=True)
            self.toogle_badge(f"Error: {str(e)}", True)
        self.page.update()

    def download_video(self):
        url = self.url_entry.value
        res = self.resolution_dropdown.value.split()[0] if self.video_audio_var.value == "Video" else None
        folder_path = self.folder_entry.value

        if self.add_audio_checkbox.value:
            current_folder = os.getcwd()
            tmp_folder = os.path.join(current_folder, "tmp")
            if not os.path.exists(tmp_folder):
                os.makedirs(tmp_folder)
            folder_path = tmp_folder

        if not url:
            self.append_to_console("Error: Please enter a YouTube URL.", error=True)
            self.toogle_badge("Please enter a YouTube URL.", True)

            return

        if not folder_path:
            self.append_to_console("Error: Please select a download folder.", error=True)
            self.toogle_badge("Please select a download folder.", True)
            return

        try:
            yt = YouTube(url, on_progress_callback=self.on_progress_callback)
            stream = yt.streams.filter(res=res, adaptive=True, only_video=True).first()
            quality = res

            if stream:
                self.append_to_console("Downloading video ...")

                file_extension = stream.default_filename.split('.')[-1]
                base_filename = stream.default_filename.replace(f".{file_extension}", "")
                custom_filename = f"{base_filename}_{quality}.{file_extension}"
                unique_filename = self.get_unique_filename(custom_filename)
                #print(unique_filename)
                output_file = stream.download(output_path=folder_path, filename=unique_filename)

                if self.cancel_flag.is_set():
                    self.append_to_console("Download video stopped.")
                    self.download_button.text = "Download"
                    self.delete_files_in_folder()
                    return

                self.append_to_console("Download video complete!")
                #self.toogle_badge("Download video complete!")

                if os.path.exists(FFMPEG_BIN) and os.path.exists(FFPROBE_BIN):
                    if output_file.endswith('.webm') and self.video_audio_var.value == "Video":
                        self.convert_to_mp4_from_webm(output_file, folder_path)

                else:
                    self.append_to_console("Missing FFMPEG-FFPROBE. Skipping Conversion", error=True)
                    self.toogle_badge("Missing FFMPEG-FFPROBE. Skipping Conversion",True)
                self.download_button.text = "Download"
                self.video_audio_var.disabled = False
                self.folder_button.disabled = False
                self.fetch_info_button.disabled = False
                self.resolution_dropdown.disabled = False
                self.url_entry.disabled = False
                self.folder_entry.disabled = False
                self.add_audio_checkbox.disabled = False
                self.pb_headline.visible= False
                self.pb.visible = False
                if not self.add_audio_checkbox.value:
                    self.toogle_badge("Download Completed!")
            else:
                self.append_to_console(f"Error: Resolution {res} not available for this video.", error=True)
                self.toogle_badge(f"Error: Resolution {res} not available for this video.", True)
                self.reset_ui()
                self.download_button.disabled = False

        except Exception as e:
            self.reset_ui()
            self.download_button.disabled = False
            self.append_to_console(f"Error: {str(e)}", error=True)
            self.toogle_badge(f"Error: {str(e)}", True)

        self.page.update()

    def merge_video_audio(self, folder_path):
        self.append_to_console("Merging audio and video...")
        self.append_to_console("It may take a while...")
        self.disable_ui()
        video_file = None
        audio_file = None
        for file in os.listdir("./tmp"):
            if file.endswith(('.webm', '.mp4')):
                video_file = os.path.join("./tmp", file)
            if file.startswith("audio"):
                audio_file = os.path.join("./tmp", file)

        if not video_file or not audio_file:
            self.append_to_console("Error: Video or audio file is missing.", error=True)
            return

        base_filename = os.path.basename(video_file).replace('.webm', '').replace('.mp4', '')
        final_output = self.get_unique_filename(os.path.join(folder_path, f"{base_filename}.mp4"))

        total_duration = self.get_total_duration(video_file)

        command = [
            FFMPEG_BIN, '-fflags', '+genpts', '-i', video_file, '-i', audio_file,
            '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', final_output
        ]
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        q = queue.Queue()
        self.enqueue = threading.Thread(target=self.enqueue_output, args=(self.process.stderr, self.process.stdout, q))
        self.enqueue.start()

        old_percentage = -1
        while True:
            try:
                line = q.get_nowait()
                print(line)
            except queue.Empty:
                if self.process.poll() is not None:
                    break
                if self.cancel_flag.is_set():
                    self.process.terminate()
                    self.append_to_console("Merging stopped.")
                    self.download_button.text = "Download"
                    self.delete_files_in_folder()
                    return
                else:
                    time.sleep(0.1)
                    continue

            if "time=" in line:
                time_str = line.split("time=")[1].split(" ")[0]
                if time_str != 'N/A':
                    hours, minutes, seconds = map(float, time_str.split(":"))
                    current_seconds = hours * 3600 + minutes * 60 + seconds
                    percentage = int((current_seconds / total_duration) * 100)
                    if percentage != old_percentage:
                        self.pb.value = percentage/100
                        self.pb_headline.value = f"Merging {int(percentage)}%"
                        self.append_to_console(f"Merging Progress: {percentage}%")
                        self.page.update()
                    old_percentage = percentage

        self.process.wait()
        self.process.terminate()

        if os.path.exists(final_output):
            self.append_to_console(f"Merging complete!")
        else:
            self.append_to_console("Error: Merging failed.", error=True)

        if os.path.exists(video_file):
            os.remove(video_file)
        if os.path.exists(audio_file):
            os.remove(audio_file)

    def enqueue_output(self, out, stdout, queue):
        for line in iter(out.readline, b''):
            if(self.process.poll() is not None):
                break
            print(line)
            queue.put(line)
        print(stdout)
        out.close()

    def convert_to_mp4_from_webm(self, webm_file, folder_path):
        self.append_to_console("Converting to MP4...")
        self.append_to_console("It may take a while...")
        self.disable_ui()
        filename = os.path.basename(webm_file)
        mp4_file = filename.replace('.webm', '.mp4')
        mp4_file = self.get_unique_filename(os.path.join(folder_path, mp4_file))

        total_duration = self.get_total_duration(webm_file)

        command = [
            FFMPEG_BIN, '-fflags', '+genpts',
            '-i', webm_file, '-r', '60', mp4_file,
        ]
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        q = queue.Queue()
        self.enqueue = threading.Thread(target=self.enqueue_output, args=(self.process.stderr, self.process.stdout, q))
        self.enqueue.start()

        old_percentage = -1
        while True:
            try:
                line = q.get_nowait()
                print(line)
            except queue.Empty:
                if self.process.poll() is not None:
                    break
                if self.cancel_flag.is_set():
                    self.process.terminate()
                    self.append_to_console("Conversion stopped.")
                    self.download_button.text = "Download"
                    self.delete_files_in_folder()
                    return
                else:
                    time.sleep(0.1)
                    continue

            if "time=" in line:
                time_str = line.split("time=")[1].split(" ")[0]
                if time_str != 'N/A':
                    hours, minutes, seconds = map(float, time_str.split(":"))
                    current_seconds = hours * 3600 + minutes * 60 + seconds
                    percentage = int((current_seconds / total_duration) * 100)
                    if percentage != old_percentage:
                        self.pb.value = percentage/100
                        self.pb_headline.value = f"Conversion {int(percentage)}%"
                        self.append_to_console(f"Conversion Progress: {percentage}%")
                        self.page.update()
                    old_percentage = percentage

        self.process.wait()
        self.process.terminate()

        if os.path.exists(mp4_file):
            self.append_to_console(f"Done!")
        #self.delete_files_in_folder()
        if os.path.exists(webm_file):
            os.remove(webm_file)

    def get_total_duration(self, file_path):
        command = [FFPROBE_BIN, '-v', 'error', '-show_entries', 'format=duration',
                  '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
        result = subprocess.run(command, capture_output=True, text=True)
        return float(result.stdout.strip())

    def convert_to_mp3_from_webm(self, webm_file, folder_path):
        self.append_to_console("Converting to MP3...")
        self.append_to_console("It may take a while...")
        filename = os.path.basename(webm_file)
        mp3_file = filename.replace('.webm', '.mp3')
        mp3_file = self.get_unique_filename(os.path.join(folder_path, mp3_file))
        total_duration = self.get_total_duration(webm_file)

        command = [
            FFMPEG_BIN,
            '-i', webm_file,
            mp3_file
        ]

        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        q = queue.Queue()
        self.queueue = threading.Thread(target=self.enqueue_output, args=(self.process.stderr, self.process.stdout, q))
        self.queueue.start()

        old_percentage = -1
        while True:
            try:
                line = q.get_nowait()
                print(line)
            except queue.Empty:
                if self.process.poll() is not None:
                    break
                if self.cancel_flag.is_set():
                    self.process.terminate()
                    self.append_to_console("Conversion stopped.")
                    self.download_button.text = "Download"
                    self.delete_files_in_folder()
                    return
                else:
                    time.sleep(0.1)
                    continue

            if "time=" in line:
                time_str = line.split("time=")[1].split(" ")[0]
                if time_str != 'N/A':
                    hours, minutes, seconds = map(float, time_str.split(":"))
                    current_seconds = hours * 3600 + minutes * 60 + seconds
                    percentage = int((current_seconds / total_duration) * 100)
                    if percentage != old_percentage:
                        self.pb.value = percentage/100
                        self.pb_headline.value = f"Conversion {int(percentage)}%"
                        self.append_to_console(f"Conversion Progress: {percentage}%")
                        self.page.update()
                    old_percentage = percentage

        self.process.wait()
        self.process.terminate()
        if os.path.exists(mp3_file):
            self.append_to_console(f"Done!")
        if os.path.exists(webm_file):
            os.remove(webm_file)

    def convert_to_mp3_from_mp4(self, mp4_file, folder_path):
        self.append_to_console("Converting to MP3...")
        self.append_to_console("It may take a while...")
        filename = os.path.basename(mp4_file)
        mp3_file = filename.replace('.mp4', '.mp3')
        mp3_file = self.get_unique_filename(os.path.join(folder_path, mp3_file))
        total_duration = self.get_total_duration(mp4_file)

        command = [
            FFMPEG_BIN,
            '-i', mp4_file,
            mp3_file
        ]

        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        q = queue.Queue()
        self.queueue = threading.Thread(target=self.enqueue_output, args=(self.process.stderr, self.process.stdout, q))
        self.queueue.start()
        old_percentage = -1
        while True:
            try:
                line = q.get_nowait()
                print(line)
            except queue.Empty:
                if self.process.poll() is not None:
                    break
                if self.cancel_flag.is_set():
                    self.process.terminate()
                    self.append_to_console("Conversion stopped.")
                    self.download_button.text = "Download"
                    self.delete_files_in_folder()
                    return
                else:
                    time.sleep(0.1)
                    continue

            if "time=" in line:
                time_str = line.split("time=")[1].split(" ")[0]
                if time_str != 'N/A':
                    hours, minutes, seconds = map(float, time_str.split(":"))
                    current_seconds = hours * 3600 + minutes * 60 + seconds
                    percentage = int((current_seconds / total_duration) * 100)
                    if percentage != old_percentage:
                        self.pb.value = percentage/100
                        self.pb_headline.value = f"Conversion {int(percentage)}%"
                        self.append_to_console(f"Conversion Progress: {percentage}%")
                    old_percentage = percentage

        self.process.wait()
        self.process.terminate()
        if os.path.exists(mp3_file):
            self.append_to_console(f"Done!")
        if os.path.exists(mp4_file):
            os.remove(mp4_file)

    def convert_to_mp3_from_m4a(self, mp4_file, folder_path):
        self.append_to_console("Converting to MP3...")
        self.append_to_console("It may take a while...")
        filename = os.path.basename(mp4_file)
        mp3_file = filename.replace('.m4a', '.mp3')
        mp3_file = self.get_unique_filename(os.path.join(folder_path, mp3_file))


        total_duration = self.get_total_duration(mp4_file)

        command = [
            FFMPEG_BIN,
            '-i', mp4_file,
            mp3_file
        ]

        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        q = queue.Queue()
        self.queueue = threading.Thread(target=self.enqueue_output, args=(self.process.stderr, self.process.stdout, q))
        self.queueue.start()
        old_percentage = -1
        while True:
            try:
                line = q.get_nowait()
                print(line)
            except queue.Empty:
                if self.process.poll() is not None:
                    break
                if self.cancel_flag.is_set():
                    self.process.terminate()
                    self.append_to_console("Conversion stopped.")
                    self.download_button.text = "Download"
                    self.delete_files_in_folder()
                    return
                else:
                    time.sleep(0.1)
                    continue

            if "time=" in line:
                time_str = line.split("time=")[1].split(" ")[0]
                if time_str != 'N/A':
                    hours, minutes, seconds = map(float, time_str.split(":"))
                    current_seconds = hours * 3600 + minutes * 60 + seconds
                    percentage = int((current_seconds / total_duration) * 100)
                    if percentage != old_percentage:
                        self.pb.value = percentage/100
                        self.pb_headline.value = f"Conversion {int(percentage)}%"
                        self.append_to_console(f"Conversion Progress: {percentage}%")
                        self.page.update()
                    old_percentage = percentage

        self.process.wait()
        self.process.terminate()
        if os.path.exists(mp3_file):
            self.append_to_console(f"Done!")
        if os.path.exists(mp4_file):
            os.remove(mp4_file)

    def on_progress_callback(self, stream, chunk, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        percentage_of_completion = bytes_downloaded / total_size * 100
        self.pb.value = percentage_of_completion/100
        self.pb_headline.value = f"Downloading {int(percentage_of_completion)}%"
        self.page.update()
        self.append_to_console(f"Downloading... {int(percentage_of_completion)}%")

    def append_to_console(self, message, error=False):
        color = ft.colors.RED if error else None
        self.console_text.controls.append(ft.Text(message, color=color))
        self.page.update()

def main(page: ft.Page):
    app = VidDownloaderApp(page)

ft.app(target=main)
