"""YouTube Music integration for Nicky AI via ytmusicapi."""
import webbrowser


class YTMusicController:
    """Controls YouTube Music using ytmusicapi for search and webbrowser for playback.

    Search works without authentication. Opening songs launches them in the
    default browser on music.youtube.com.
    """

    BASE_URL = "https://music.youtube.com/watch?v="
    BROWSE_URL = "https://music.youtube.com"

    def __init__(self, config: dict = None):
        self._ytm = None
        self._available = False
        self._last_video_id: str = ""
        self._last_title: str = ""
        self._init()

    def _init(self):
        try:
            from ytmusicapi import YTMusic
            self._ytm = YTMusic()  # unauthenticated — search only
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self):
        return self._available

    def search_and_play(self, query: str) -> str:
        if not self._available:
            return "YouTube Music is not available. Run: pip install ytmusicapi"
        try:
            results = self._ytm.search(query, filter="songs", limit=1)
            if not results:
                results = self._ytm.search(query, limit=1)
            if not results:
                return f"Couldn't find '{query}' on YouTube Music."
            top = results[0]
            video_id = top.get("videoId", "")
            title = top.get("title", query)
            artists = ", ".join(a["name"] for a in top.get("artists", []))
            self._last_video_id = video_id
            self._last_title = f"{title} — {artists}" if artists else title
            url = f"{self.BASE_URL}{video_id}"
            webbrowser.open(url)
            return f"▶ Opening on YouTube Music: {self._last_title}"
        except Exception as e:
            return f"Couldn't play '{query}': {e}"

    def open_home(self) -> str:
        webbrowser.open(self.BROWSE_URL)
        return "▶ Opened YouTube Music in your browser."

    def get_now_playing(self) -> str:
        if self._last_title:
            return f"▶ Last opened: {self._last_title}"
        return "Nothing opened yet. Try: 'play [song] on youtube music'"

    def play_pause(self) -> str:
        """Send media play/pause key via keyboard if possible."""
        try:
            import pyautogui
            pyautogui.press("playpause")
            return "⏯ Sent play/pause key."
        except Exception:
            return "Use the space bar in your browser to pause/resume."

    def next_track(self) -> str:
        try:
            import pyautogui
            pyautogui.press("nexttrack")
            return "⏭ Sent next track key."
        except Exception:
            return "Use the Next button in your browser."

    def prev_track(self) -> str:
        try:
            import pyautogui
            pyautogui.press("prevtrack")
            return "⏮ Sent previous track key."
        except Exception:
            return "Use the Previous button in your browser."

    def set_volume(self, level: int) -> str:
        return f"Use your system volume or the YouTube Music player to set volume to {level}%."

