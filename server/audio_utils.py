from pydub import AudioSegment

# Allowed audio file extensions
ALLOWED_EXTENSIONS = {'wav'}

# Check if the file is a valid audio file
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Get the length of the audio file
def get_audio_length(file_path):
    audio = AudioSegment.from_wav(file_path)
    return len(audio)

# Validate the audio file
# The audio file must be 32-bit and 96KHz stereo audio
def validate_audio(file_path):
    audio = AudioSegment.from_wav(file_path)
    if audio.sample_width != 4:
        return False  # Not 32-bit
    if audio.frame_rate != 96000:
        return False  # Not 96KHz
    if audio.channels != 2:
        return False
    return True