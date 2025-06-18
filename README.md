# VidDownloader

VVidDownloader is a simple desktop application that acts as a UI wrapper for `pytube` and `pytubefix`, making it easy to download YouTube videos and audio. The application offers an intuitive interface built with `customtkinter`, allowing users to download and convert media files without needing to interact with the command line. It supports various resolutions and formats, utilizing `ffmpeg` for media conversion tasks.


<img src="https://github.com/AndreaSillano/VidDownloader/blob/main/images/exampleImage.png" width="50%" height="50%">

## Features

- **Download Videos and Audio**: Choose to download video with audio or audio-only from YouTube.
- **Multiple Resolutions and Bitrates**: Select from available video resolutions or audio bitrates.
- **Automatic Conversion**: Converts WebM to MP4 or MP3 formats using FFmpeg.
- **Custom Download Folder**: Choose where to save your downloaded files.
- **Progress Monitoring**: View the download and conversion progress in real-time.
- **Cancellation**: Ability to cancel downloads or conversions in progress.

## Installation

### Prerequisites

- Python 3.x
- `pip` package manager

### Clone the Repository

```bash
git clone https://github.com/AndreaSillano/VidDownloader.git
cd VidDownloader
```

## Install dependency
Use the provided requirements.txt file to install the necessary Python packages:
```python
pip install -r requirements.txt
```

## FFmpeg

This project requires [FFmpeg](https://ffmpeg.org/) for video and audio processing. FFmpeg is a powerful multimedia framework that can decode, encode, transcode, mux, demux, stream, filter, and play almost anything that humans and machines have created.

### Installation

To use FFmpeg and FFProbe with this project, you need to have compiled binary installed on your system (by cloning from this repository those are already included). Here's how you can install it:

1. Download the latest executable version of FFmpeg from the [official website](https://ffmpeg.org/download.html) .
2. Extract the downloaded ZIP file to the resources folder.

# Run the Application

Start the application by running:
```python
python3 YTDownloader.py
```


# Known Issues
- Sometimes during conversions percetages reach 99% and stops althought the video is correctly converted. If this happens just close the program.

## Contributing

Contributions are welcome! If you have any ideas, suggestions, or issues, please feel free to open an issue or create a pull request. We appreciate all forms of contributions, whether it's improving documentation, fixing bugs, or adding new features.



## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## Legal and Ethical Considerations

When using this software, please be mindful of the following legal and ethical considerations:

- **Copyright Compliance**: Ensure you have the right to download and use the content from YouTube. This software is intended for personal use and educational purposes only. Downloading copyrighted material without permission may violate copyright laws.

- **YouTube Terms of Service**: Adhere to YouTube's Terms of Service and any other relevant agreements. The use of this software for purposes that contravene YouTube's policies, such as downloading videos for redistribution or commercial use, is not supported.

- **Local Laws**: Be aware of and comply with any local laws or regulations related to media downloading and content use in your jurisdiction. The responsibility for ensuring compliance with these laws rests with the user.

- **Ethical Use**: Use this software responsibly and ethically. Avoid using it for purposes that could harm content creators or violate their rights.

By using this software, you agree to adhere to these guidelines and accept responsibility for your own actions regarding the use of downloaded content.


## Acknowledgements



- [**pytube**](https://github.com/pytube/pytube): Special thanks to `pytube` for handling YouTube downloads and helping make this project possible.

- [**pytubefix**](https://github.com/JuanBindez/pytubefix): Special thanks to `pytubefix` for handling YouTube downloads and helping make this project possible and correct the pytube version.

- [**FFmpeg**](https://ffmpeg.org/download.html): For providing powerful media conversion tools, allowing seamless conversion of video and audio formats.

- [**customtkinter**](https://github.com/tomschimansky/customtkinter): For offering a modern and customizable design framework for tkinter, enhancing the user interface of this project.


This markdown provides a clear and organized structure for the "Contributing," "License," and "Acknowledgements" sections, making it easy for others to understand how they can contribute to the project and giving proper credit to the libraries and tools used.
