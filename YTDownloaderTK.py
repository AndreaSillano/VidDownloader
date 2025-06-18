import customtkinter as ctk
from tkinter import filedialog
from pytubefix import YouTube
import ssl
import subprocess
import threading
from PIL import ImageTk, Image
import requests
from io import BytesIO
import os
import queue
import shutil


# Global flag to indicate cancellation
cancel_flag = threading.Event()

FFMPEG_BIN = os.path.join(os.path.dirname(__file__), 'resources/ffmpeg')
FFPROBE_BIN = os.path.join(os.path.dirname(__file__), 'resources/ffprobe')


ssl._create_default_https_context = ssl._create_unverified_context

def browse_folder():
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        folder_entry.delete(0, ctk.END)
        folder_entry.insert(0, folder_selected)
        append_to_console(f"Download folder set to {folder_selected}")
        download_button.configure(state="normal")
def truncate_text(text, max_length=20):
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    return text

def fetch_video_info():
    url = url_entry.get()
    if not url:
        append_to_console("Error: Please enter a YouTube URL.", error=True)
        return

    try:
        append_to_console("Fetching video information. Please wait...")
        yt = YouTube(url)

        # Display the video thumbnail
        img_url = yt.thumbnail_url
        response = requests.get(img_url)
        img_data = BytesIO(response.content)
        img = Image.open(img_data)
        img = img.resize((160, 90), Image.LANCZOS)
        thumbnail_image = ImageTk.PhotoImage(img)
        tk_img = ctk.CTkImage(img, size=(160,90))
        thumbnail_label.configure(image=tk_img)
        thumbnail_label.image = thumbnail_image
        thumbnail_label.configure(text="")

        # Display video name, duration and size
        video_name = truncate_text(yt.title)
        video_name_label.configure(text=f"Video Name: {video_name}")
        video_duration = yt.length
        minutes, seconds = divmod(video_duration, 60)
        duration_label.configure(text=f"Duration: {minutes:02}:{seconds:02}")

        # Fetch and display resolutions
        if video_audio_var.get() == "Video":
            streams = yt.streams.order_by('resolution').filter(only_video=True)
            stream_size = streams[0].filesize
            if stream_size < 1024 * 1024:
                size_label.configure(text=f"Download size: {stream_size // 1024} KB")
            else:
                size_label.configure(text=f"Download size: {stream_size // (1024 * 1024)} MB")

            #resolutions = [stream.resolution for stream in streams if stream.resolution]
            #resolutions = list(dict.fromkeys(resolutions))  # Remove duplicates while preserving order
            resolutions = []
            for stream in streams:
                if stream.resolution:
                    if stream.mime_type == "video/webm":
                        resolutions.append(f"{stream.resolution} (WebM - Conversion Needed)")
                    else:
                        resolutions.append(stream.resolution)
            if resolutions:
                resolution_combobox.configure(values=resolutions)
                resolution_combobox.set(resolutions[-1])  # Default to highest resolution
                resolution_combobox.configure(state="normal")
                append_to_console("Resolutions fetched! Select one to proceed.")
            else:
                append_to_console("Error: No streams found for this URL.", error=True)

        else:
            # Disable the resolution combobox for audio-only
            # Fetch audio-only streams
            streams = yt.streams.filter(only_audio=True).order_by('abr')
            stream_size = streams[0].filesize
            if stream_size < 1024 * 1024:
                size_label.configure(text=f"Download size: {stream_size // 1024} KB")
            else:
                size_label.configure(text=f"Download size: {stream_size // (1024 * 1024)} MB")

            # Fetch available audio bitrates
            audio_bitrates = []
            for stream in streams:
                if stream.abr:
                    if stream.mime_type == "audio/webm":
                        audio_bitrates.append(f"{stream.abr} (WebM - Conversion Needed)")
                    else:
                        audio_bitrates.append(stream.abr)

            # Update the combobox and notify the user
            if audio_bitrates:
                resolution_combobox.configure(values=audio_bitrates)
                resolution_combobox.set(audio_bitrates[-1])  # Default to highest bitrate
                resolution_combobox.configure(state="normal")
                append_to_console("Audio bitrates fetched! Select one to proceed.")
            else:
                append_to_console("Error: No audio streams found for this URL.", error=True)

        # Show the info_frame
        info_frame.grid(row=4, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")

    except Exception as e:
        append_to_console(f"Error: {str(e)}", error=True)

def on_resolution_selected(value):
    folder_button.configure(state="normal")
    append_to_console(f"Resolution set to {value}")

def reset_ui():
    url_entry.delete(0, ctk.END)
    folder_entry.delete(0, ctk.END)
    download_button.configure(text="Download")
    thumbnail_label.configure(image="", text="")  # Clear thumbnail
    size_label.configure(text="Download size: N/A")
    duration_label.configure(text="Duration: N/A")
    resolution_combobox.set([])
    resolution_combobox.configure(values=[], state="disabled")
    #cancel_flag.clear()
    if video_audio_var.get() != "Video":
        folder_button.configure(state="normal")
        add_audio_checkbox.configure(state="normal")
        #append_to_console("Audio only selected!")
    else:
        #append_to_console("Video with audio selected!")
        folder_button.configure(state="disabled")
        add_audio_checkbox.configure(state="disabled")

    download_button.configure(state="disabled")
    info_frame.grid_forget()  # Hide info_frame

def on_video_audio_change(value):
    reset_ui()
    if value == 'Audio':
        add_audio_checkbox.configure(state = "disabled")
        add_audio_var.set('on')
    else:
        add_audio_checkbox.configure(state = "normal")
        add_audio_var.set('off')


def get_unique_filename(filepath):
    """
    Generate a unique filename by appending a number if the file already exists.
    """
    if not os.path.exists(filepath):
        return filepath

    base, ext = os.path.splitext(filepath)
    counter = 1
    new_filepath = f"{base}_{counter}{ext}"

    while os.path.exists(new_filepath):
        counter += 1
        new_filepath = f"{base}_{counter}{ext}"

    return new_filepath

def delete_files_in_folder(folder_path):
    if os.path.exists(folder_path):
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)  # Delete the file
    else:
        print(f"The folder '{folder_path}' does not exist.")

def toggle_download():
    global download_thread
    global download_only_audio_thread
    global worker_thread

    if download_button.cget("text") == "Download":
        current_folder = os.getcwd()  # Get the current working directory
        tmp_folder = os.path.join(current_folder, "tmp")
        if not os.path.exists(tmp_folder):
            os.makedirs(tmp_folder)
        else:
            delete_files_in_folder(tmp_folder)
        cancel_flag.clear()
        if video_audio_var.get() == "Video":
            download_thread = threading.Thread(target=download_video)
            download_thread.start()
            if add_audio_var.get() == 'on':
                if os.path.exists(FFMPEG_BIN) and os.path.exists(FFPROBE_BIN):
                    download_only_audio_thread = threading.Thread(target=download_audio)
                    download_only_audio_thread.start()
                    worker_thread = threading.Thread(target=wait_for_download_completion)
                    worker_thread.start()
                else:
                    append_to_console("Missing FFMPEG-FFPROBE. Cannot merge audio - Downloading Video", error=True)
                    add_audio_var.set('off')

        else:
            download_thread = threading.Thread(target=download_audio)
            download_thread.start()

    else:
        cancel_flag.set()  # Signal cancellation
        if download_thread and download_thread.is_alive():
            download_thread.join(timeout=5)
        if download_only_audio_thread and download_only_audio_thread.is_alive():
            download_only_audio_thread.join(timeout=5)
        if worker_thread and worker_thread.is_alive():
            worker_thread.join(timeout = 5)

        #reset_ui()
        download_button.configure(state="normal")
        folder_button.configure(state="normal")
        fetch_info_button.configure(state="normal")
        resolution_combobox.configure(state="normal")
        url_entry.configure(state="normal")
        folder_entry.configure(state="normal")
        add_audio_checkbox.configure(state="normal")

def wait_for_download_completion():
    if download_thread:
        download_thread.join()

    if download_only_audio_thread:
        download_only_audio_thread.join()

    # After both threads finish, merge if needed
    if add_audio_checkbox.get() == "on":
        try:
            merge_video_audio(folder_path=folder_entry.get())
            append_to_console("Download complete!")

            #download_button.configure(text="Download")
        except Exception as e:
            reset_ui()
            download_button.configure(state="normal")
            append_to_console(f"Error: {str(e)}", error=True)

def download_audio():
    url = url_entry.get()
    abr = resolution_combobox.get().split()[0] if video_audio_var.get() != "Video" else None
    folder_path = folder_entry.get()

    if add_audio_var.get() == 'on':
        current_folder = os.getcwd()  # Get the current working directory
        tmp_folder = os.path.join(current_folder, "tmp")
        if not os.path.exists(tmp_folder):
            os.makedirs(tmp_folder)
        folder_path = tmp_folder


    if not url:
        append_to_console("Error: Please enter a YouTube URL.", error=True)
        return

    if not folder_path:
        append_to_console("Error: Please select a download folder.", error=True)
        return

    try:
        download_button.configure(text="Cancel")
        folder_button.configure(state="disabled")
        fetch_info_button.configure(state="disabled")
        resolution_combobox.configure(state="disabled")
        url_entry.configure(state="disabled")
        folder_entry.configure(state="disabled")
        add_audio_checkbox.configure(state="disabled")


        yt = YouTube(url, on_progress_callback=on_progress_callback if add_audio_var.get() == "off" else None)

        stream = yt.streams.filter(only_audio=True, abr=abr).order_by('abr').first()
        if abr != None:
            quality = abr
        else:
            quality = 'tmp'

        if stream:
            append_to_console("Downloading audio...")
            root.update_idletasks()

            file_extension = stream.default_filename.split('.')[-1]
            base_filename = stream.default_filename.replace(f".{file_extension}", "")
            custom_filename = f"{base_filename}_{quality}.{file_extension}"
            if add_audio_var.get() == 'on':
                custom_filename = f"audio_{custom_filename}"
            unique_filename = get_unique_filename(custom_filename)
            # Perform the download with the new filename
            output_file = stream.download(output_path=folder_path, filename=unique_filename)
            if cancel_flag.is_set():  # Check if cancellation was requested
                append_to_console("Download audio stopped.")
                download_button.configure(text="Download")
                if os.path.exists(output_file):
                    os.remove(output_file)
                return

            append_to_console("Download audio complete!")

            if os.path.exists(FFMPEG_BIN) and os.path.exists(FFPROBE_BIN):
                if output_file.endswith('.webm') and video_audio_var.get() != "Video":
                    convert_to_mp3_from_webm(output_file, folder_path)

                elif output_file.endswith('.mp4') and video_audio_var.get() != "Video":
                    convert_to_mp3_from_mp4(output_file, folder_path)
            else:
                append_to_console("Missing FFMPEG-FFPROBE. Skipping Conversion", error=True)

            download_button.configure(state="normal")
            download_button.configure(text = "Download")
            folder_button.configure(state="normal")
            fetch_info_button.configure(state="normal")
            resolution_combobox.configure(state="normal")
            url_entry.configure(state="normal")
            folder_entry.configure(state="normal")

        else:
            reset_ui()
            download_button.configure(state="normal")
    except Exception as e:
        reset_ui()
        download_button.configure(state="normal")

        append_to_console(f"Error: {str(e)}", error=True)

def download_video():
    url = url_entry.get()
    res = resolution_combobox.get().split()[0] if video_audio_var.get() == "Video" else None
    folder_path = folder_entry.get()
    if add_audio_var.get() == 'on':
        current_folder = os.getcwd()  # Get the current working directory
        tmp_folder = os.path.join(current_folder, "tmp")
        if not os.path.exists(tmp_folder):
            os.makedirs(tmp_folder)
        folder_path = tmp_folder

    if not url:
        append_to_console("Error: Please enter a YouTube URL.", error=True)
        return

    if not folder_path:
        append_to_console("Error: Please select a download folder.", error=True)
        return

    try:
        download_button.configure(text="Cancel")
        folder_button.configure(state="disabled")
        fetch_info_button.configure(state="disabled")
        resolution_combobox.configure(state="disabled")
        url_entry.configure(state="disabled")
        folder_entry.configure(state="disabled")
        add_audio_checkbox.configure(state="disabled")

        yt = YouTube(url, on_progress_callback=on_progress_callback)
        stream = yt.streams.filter(res=res, adaptive=True, only_video=True).first()
        quality = res

        if stream:
            append_to_console("Downloading video ...")
            root.update_idletasks()

            file_extension = stream.default_filename.split('.')[-1]
            base_filename = stream.default_filename.replace(f".{file_extension}", "")
            custom_filename = f"{base_filename}_{quality}.{file_extension}"
            unique_filename = get_unique_filename(custom_filename)
            # Perform the download with the new filename
            output_file = stream.download(output_path=folder_path, filename=unique_filename)
            if cancel_flag.is_set():  # Check if cancellation was requested
                append_to_console("Download video stopped.")
                download_button.configure(text="Download")
                if os.path.exists(output_file):
                    os.remove(output_file)
                #reset_ui()
                return

            append_to_console("Download video complete!")

            if os.path.exists(FFMPEG_BIN) and os.path.exists(FFPROBE_BIN):
                if output_file.endswith('.webm') and video_audio_var.get() == "Video":
                    convert_to_mp4_from_webm(output_file, folder_path)
            else:
                append_to_console("Missing FFMPEG-FFPROBE. Skipping Conversion", error=True)

            download_button.configure(state="normal")
            download_button.configure(text = "Download")
            folder_button.configure(state="normal")
            fetch_info_button.configure(state="normal")
            resolution_combobox.configure(state="normal")
            url_entry.configure(state="normal")
            folder_entry.configure(state="normal")
            add_audio_checkbox.configure(state="normal")

        else:
            append_to_console(f"Error: Resolution {res} not available for this video.", error=True)
            reset_ui()
            download_button.configure(state="normal")
    except Exception as e:
        reset_ui()
        download_button.configure(state="normal")

        append_to_console(f"Error: {str(e)}", error=True)

def merge_video_audio(folder_path):
    append_to_console("Merging audio and video...")
    append_to_console("It may take a while...")
    root.update_idletasks()
    old_percetage = -1

    video_file = None
    audio_file = None
    for file in os.listdir("./tmp"):
        if file.endswith(('.webm', '.mp4')):  # Adjust video extensions if necessary
            video_file = os.path.join("./tmp", file)
        if file.startswith("audio"):  # Assume the audio file starts with 'audio' and has any extension
            audio_file = os.path.join("./tmp", file)

    if not video_file or not audio_file:
        append_to_console("Error: Video or audio file is missing.", error=True)
        return

    base_filename = os.path.basename(video_file).replace('.webm', '').replace('.mp4', '')
    final_output = get_unique_filename(os.path.join(folder_path, f"{base_filename}.mp4"))

    total_duration = get_total_duration(video_file)

    command = [
        FFMPEG_BIN, '-fflags', '+genpts', '-i', video_file, '-i', audio_file,
        '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', final_output
    ]
    process = subprocess.Popen(command, stdout= subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Create a queue to hold stdout and stderr lines
    q = queue.Queue()
    threading.Thread(target=enqueue_output, args=(process.stderr, process.stdout,q)).start()

    while True:
        try:
            line = q.get_nowait()
            print(line)
        except queue.Empty:
            if process.poll() is not None:  # Process has finished
                break
            if cancel_flag.is_set():  # Check if cancellation was requested
                process.terminate()
                append_to_console("Merging stopped.")
                download_button.configure(text="Download")

                if os.path.exists(video_file):
                    os.remove(video_file)
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                #reset_ui()
                return
            else:
                root.update()  # Keep the UI responsive
                continue

        #append_to_console(line.strip())
        if "time=" in line:
            time_str = line.split("time=")[1].split(" ")[0]
            if time_str != 'N/A':
                hours, minutes, seconds = map(float, time_str.split(":"))
                current_seconds = hours * 3600 + minutes * 60 + seconds
                percentage = int((current_seconds / total_duration) * 100)
                if percentage != old_percetage:
                    append_to_console(f"Merging Progress: {percentage}%")
                old_percetage = percentage

    process.wait()
    if os.path.exists(final_output):
        append_to_console(f"Merging complete!")
    else:
        append_to_console("Error: Merging failed.", error=True)


    if os.path.exists(video_file):
        os.remove(video_file)
    if os.path.exists(audio_file):
        os.remove(audio_file)

def enqueue_output(out, stdout, queue):

    for line in iter(out.readline, b''):
        print(line)
        queue.put(line)
    print(stdout)
    out.close()

def convert_to_mp4_from_webm(webm_file, folder_path):
    append_to_console("Converting to MP4...")
    append_to_console("It may take a while...")
    root.update_idletasks()
    old_percetage = -1

    mp4_file = webm_file.replace('.webm', '.mp4')
    mp4_file = get_unique_filename(os.path.join(folder_path, mp4_file))

    total_duration = get_total_duration(webm_file)

    command = [
        FFMPEG_BIN, '-fflags', '+genpts',
        '-i', webm_file, '-r', '60', mp4_file,
    ]
    process = subprocess.Popen(command, stdout= subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Create a queue to hold stdout and stderr lines
    q = queue.Queue()
    threading.Thread(target=enqueue_output, args=(process.stderr, process.stdout,q)).start()

    while True:
        try:
            line = q.get_nowait()
            print(line)
        except queue.Empty:
            if process.poll() is not None:  # Process has finished
                break
            if cancel_flag.is_set():  # Check if cancellation was requested
                process.terminate()
                append_to_console("Conversion stopped.")
                download_button.configure(text="Download")

                if os.path.exists(mp4_file):
                    os.remove(mp4_file)
                if os.path.exists(webm_file):
                    os.remove(webm_file)
                #reset_ui()
                return
            else:
                root.update()  # Keep the UI responsive
                continue

        #append_to_console(line.strip())
        if "time=" in line:
            time_str = line.split("time=")[1].split(" ")[0]
            if time_str != 'N/A':
                hours, minutes, seconds = map(float, time_str.split(":"))
                current_seconds = hours * 3600 + minutes * 60 + seconds
                percentage = int((current_seconds / total_duration) * 100)
                if percentage != old_percetage:
                    append_to_console(f"Conversion Progress: {percentage}%")
                old_percetage = percentage

    process.wait()

    if os.path.exists(mp4_file):
        append_to_console(f"Done!")
    if os.path.exists(webm_file):
        os.remove(webm_file)  # Remove the original file
       # append_to_console(f"Original file {webm_file} removed")

def get_total_duration(file_path):
    command = [FFPROBE_BIN, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
    result = subprocess.run(command, capture_output=True, text=True)
    return float(result.stdout.strip())

def convert_to_mp3_from_webm(webm_file, folder_path):
    append_to_console("Converting to MP3...")
    append_to_console("It may take a while...")
    root.update_idletasks()
    old_percetage = -1

    mp3_file = webm_file.replace('.webm', '.mp3')
    mp3_file = get_unique_filename(os.path.join(folder_path, mp3_file))
    total_duration = get_total_duration(webm_file)

    command = [
        FFMPEG_BIN,
        '-i', webm_file,
        mp3_file
    ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Create a queue to hold stdout and stderr lines
    q = queue.Queue()
    threading.Thread(target=enqueue_output, args=(process.stderr,  process.stdout,q)).start()

    while True:
        try:
            line = q.get_nowait()
            print(line)
        except queue.Empty:
            if process.poll() is not None:  # Process has finished
                break
            if cancel_flag.is_set():  # Check if cancellation was requested
                process.terminate()
                append_to_console("Conversion stopped.")
                download_button.configure(text="Download")

                if os.path.exists(mp3_file):
                    os.remove(mp3_file)
                if os.path.exists(webm_file):
                    os.remove(webm_file)
                #reset_ui()
                return
            else:
                root.update()  # Keep the UI responsive
                continue

        #append_to_console(line.strip())
        if "time=" in line:
            time_str = line.split("time=")[1].split(" ")[0]
            if time_str != 'N/A':
                hours, minutes, seconds = map(float, time_str.split(":"))
                current_seconds = hours * 3600 + minutes * 60 + seconds
                percentage = int((current_seconds / total_duration) * 100)
                if percentage != old_percetage:
                    append_to_console(f"Conversion Progress: {percentage}%")
                old_percetage = percentage

    process.wait()
    if os.path.exists(mp3_file):
        append_to_console(f"Done!")
    if os.path.exists(webm_file):
        os.remove(webm_file)  # Remove the original file
       # append_to_console(f"Original file {webm_file} removed")

def convert_to_mp3_from_mp4(mp4_file,folder_path):
    append_to_console("Converting to MP3...")
    append_to_console("It may take a while...")
    root.update_idletasks()
    old_percetage = -1

    mp3_file = mp4_file.replace('.mp4', '.mp3')
    mp3_file = get_unique_filename(os.path.join(folder_path, mp4_file))
    total_duration = get_total_duration(mp4_file)

    command = [
        FFMPEG_BIN,
        '-i', mp4_file,
        mp3_file
    ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Create a queue to hold stdout and stderr lines
    q = queue.Queue()
    threading.Thread(target=enqueue_output, args=(process.stderr,  process.stdout,q)).start()

    while True:
        try:
            line = q.get_nowait()
            print(line)
        except queue.Empty:
            if process.poll() is not None:  # Process has finished
                break
            if cancel_flag.is_set():  # Check if cancellation was requested
                process.terminate()
                append_to_console("Conversion stopped.")
                download_button.configure(text="Download")

                if os.path.exists(mp3_file):
                    os.remove(mp3_file)
                if os.path.exists(mp4_file):
                    os.remove(mp4_file)
                return
            else:
                root.update()  # Keep the UI responsive
                continue

        #append_to_console(line.strip())
        if "time=" in line:
            time_str = line.split("time=")[1].split(" ")[0]
            if time_str != 'N/A':
                hours, minutes, seconds = map(float, time_str.split(":"))
                current_seconds = hours * 3600 + minutes * 60 + seconds
                percentage = int((current_seconds / total_duration) * 100)
                if percentage != old_percetage:
                    append_to_console(f"Conversion Progress: {percentage}%")
                old_percetage = percentage

    process.wait()
    if os.path.exists(mp3_file):
        append_to_console(f"Done!")
    if os.path.exists(mp4_file):
        os.remove(mp4_file)  # Remove the original file
       # append_to_console(f"Original file {webm_file} removed")

def on_progress_callback(stream, chunk, bytes_remaining):
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    percentage_of_completion = bytes_downloaded / total_size * 100
    append_to_console(f"Downloading... {int(percentage_of_completion)}%")

def append_to_console(message, error=False):
    console_text.configure(state="normal")

    if error:
        console_text.insert(ctk.END, message + "\n", "error")
    else:
        console_text.insert(ctk.END, message + "\n")

    console_text.tag_config("error", foreground="red")
    console_text.configure(state="disabled")
    console_text.yview(ctk.END)

def center_window(window, width, height):
    # Get the screen width and height
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    # Calculate position x, y coordinates
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)

    # Set the window size and position
    window.geometry(f'{width}x{height}+{x}+{y}')
# Create the main window
root = ctk.CTk()
root.title("VidDownloader")
root.geometry('520x600')  # Increased size of the window
root.resizable(False, False)  # Make window non-resizable
center_window(root, 520, 600)

# Create the URL entry
url_label = ctk.CTkLabel(root, text="YouTube URL:")
url_label.grid(column=0, row=1, padx=10, pady=10, sticky="w")
url_entry = ctk.CTkEntry(root, width=350)
url_entry.grid(column=1, row=1, padx=10, pady=10, sticky="ew")

# Video/Audio selection radio buttons
video_audio_var = ctk.StringVar(value="Video")

# Radio buttons for selecting between Video with audio and Audio only
video_radio = ctk.CTkRadioButton(root, text="Video with audio", variable=video_audio_var, value="Video", command=lambda: on_video_audio_change("Video"))
audio_radio = ctk.CTkRadioButton(root, text="Audio only", variable=video_audio_var, value="Audio", command=lambda: on_video_audio_change("Audio"))

# Placing the radio buttons in the grid with adjusted columnspan and padx for centering
video_radio.grid(row=0, column=1, columnspan=3, padx=10, pady=10, sticky="we")
audio_radio.grid(row=0, column=2, columnspan=3, padx=10, pady=10, sticky="we")

# Fetch video info button
fetch_info_button = ctk.CTkButton(root, text="Fetch Info", command=fetch_video_info)
fetch_info_button.grid(column=2, row=1, padx=10, pady=10, sticky="ew")

# Create the info_frame initially hidden
info_frame = ctk.CTkFrame(root)
info_frame.grid(row=4, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
info_frame.grid_columnconfigure(0, weight=1)
info_frame.grid_columnconfigure(1, weight=1)

# Create and place the widgets within info_frame

thumbnail_label = ctk.CTkLabel(info_frame, text="Thumbnail Placeholder", anchor="center")
thumbnail_label.grid(row=0, column=0, rowspan=3, padx=10, pady=10, sticky="nsew")

video_name_label = ctk.CTkLabel(info_frame, text="Video name: N/A", anchor="w")
video_name_label.grid(row=0, column=1, padx=10, pady=5, sticky="w")

size_label = ctk.CTkLabel(info_frame, text="Download size: N/A", anchor="w")
size_label.grid(row=1, column=1, padx=10, pady=5, sticky="w")

duration_label = ctk.CTkLabel(info_frame, text="Duration: N/A", anchor="w")
duration_label.grid(row=2, column=1, padx=10, pady=5, sticky="w")

# Create the resolution dropdown
resolution_label = ctk.CTkLabel(root, text="Resolution:")
resolution_label.grid(row=6, column=0, padx=10, pady=10, sticky="w")
resolution_combobox = ctk.CTkComboBox(root, state="disabled", command=on_resolution_selected)
resolution_combobox.set("Select a resolution")
resolution_combobox.grid(row=6, column=1, padx=10, pady=10, sticky="ew")
add_audio_var = ctk.StringVar(value="on")  # Default value set to "on" (checked)
add_audio_checkbox = ctk.CTkCheckBox(root,  text="with Audio", onvalue="on", offvalue="off", variable=add_audio_var)
add_audio_checkbox.grid(row = 6, column = 2, padx=10, pady=10, sticky="ew")


# Create the folder selection
folder_label = ctk.CTkLabel(root, text="Download Folder:")
folder_label.grid(row=7, column=0, padx=10, pady=10, sticky="w")
folder_entry = ctk.CTkEntry(root, width=350, state="normal")
folder_entry.grid(row=7, column=1, padx=10, pady=10, sticky="ew")
folder_button = ctk.CTkButton(root, text="Browse", command=browse_folder, state="disabled")
folder_button.grid(row=7, column=2, padx=10, pady=10, sticky="ew")

# Create the download button
download_button = ctk.CTkButton(root, text="Download", command=toggle_download, state="disabled")
download_button.grid(row=8, column=0, columnspan=3, padx=10, pady=20, sticky="ew")

# Create the console area
console_frame = ctk.CTkFrame(root)
console_frame.grid(row=9, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
console_title = ctk.CTkLabel(console_frame, text="Console", font=("Arial", 12, "bold"))
console_title.pack(anchor="w", padx=5, pady=5)
console_text = ctk.CTkTextbox(console_frame, height=5, width=60, state="disabled")
console_text.pack(side="left", fill="both", expand=True, padx=5, pady=5)

# Adjust column weights for resizing
root.grid_columnconfigure(1, weight=1)
root.grid_rowconfigure(9, weight=1)  # Allow console row to expand
info_frame.grid_forget()
# Run the application
root.mainloop()
