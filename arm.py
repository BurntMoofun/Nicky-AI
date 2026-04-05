try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _SKLEARN_OK = True
except ImportError:
    _SKLEARN_OK = False
    TfidfVectorizer = None
    cosine_similarity = None


# Virtual Environment - represents the workspace
class Environment:
    def __init__(self):
        self.objects = []  # List of objects in the workspace
        self.arm_position = {"x": 0, "y": 0, "z": 0}  # Arm's current position
    
    def add_object(self, name, distance, angle, size="small"):
        """Add an object to the environment"""
        obj = {
            "name": name,
            "distance": distance,
            "angle": angle,
            "size": size,
            "held": False,
            "on_top_of": None  # Track if this object is on top of another
        }
        self.objects.append(obj)
        return f"Added {name} to the environment ({distance}cm away, {angle}°)"
    
    def remove_object(self, name):
        """Remove an object from the environment"""
        for obj in self.objects:
            if obj["name"].lower() == name.lower():
                self.objects.remove(obj)
                return f"Removed {name}"
        return f"{name} not found"
    
    def list_objects(self):
        """Show all objects in the environment"""
        if not self.objects:
            return "No objects in the environment. Add some first!"
        
        result = "Objects in workspace:\n"
        for obj in self.objects:
            if obj["held"]:
                status = "(in gripper)"
            elif obj["on_top_of"]:
                status = f"(on top of {obj['on_top_of']})"
            else:
                status = "(on ground)"
            result += f"  - {obj['name']}: {obj['distance']}cm, angle {obj['angle']}° {status}\n"
        return result.strip()
    
    def grab_object(self, name):
        """Mark an object as being held"""
        for obj in self.objects:
            if obj["name"].lower() == name.lower():
                obj["held"] = True
                return True
        return False
    
    def drop_object(self, name):
        """Mark an object as no longer held"""
        for obj in self.objects:
            if obj["name"].lower() == name.lower():
                obj["held"] = False
                return True
        return False
    
    def place_on_object(self, obj_name, target_name):
        """Place one object on top of another"""
        obj = self.find_object(obj_name)
        target = self.find_object(target_name)
        
        if obj and target:
            obj["on_top_of"] = target_name
            obj["held"] = False
            return True
        return False
    
    def remove_from_object(self, obj_name):
        """Remove object from being on top of something"""
        obj = self.find_object(obj_name)
        if obj:
            obj["on_top_of"] = None
            return True
        return False
    
    def find_object(self, name):
        """Find and return an object by exact name match."""
        for obj in self.objects:
            if name.lower() == obj["name"].lower():
                return obj
        return None


# Vision system for detecting objects in 180-degree field of view
class VisionSystem:
    def __init__(self):
        self.fov = 180  # Field of view in degrees
        self.detected_objects = []
        self.camera_active = False
        
    def activate_camera(self):
        """Turn on camera"""
        self.camera_active = True
        return "Camera activated. Scanning environment..."
    
    def deactivate_camera(self):
        """Turn off camera"""
        self.camera_active = False
        self.detected_objects = []
        return "Camera deactivated."
    
    def scan(self):
        """Simulate scanning for objects (will use real camera later)"""
        if not self.camera_active:
            return "Camera is not active."
        
        # Simulated object detection
        # In final version, this will process real camera feed
        self.detected_objects = [
            {"name": "object_1", "distance": 30, "angle": -45},
            {"name": "object_2", "distance": 50, "angle": 0},
            {"name": "object_3", "distance": 40, "angle": 45}
        ]
        return f"Scan complete. {len(self.detected_objects)} objects detected."
    
    def get_objects_in_view(self):
        """Return what the camera sees"""
        if not self.camera_active:
            return "Camera is offline."
        
        if not self.detected_objects:
            return "No objects in view."
        
        result = "Objects detected in 180° field of view:\n"
        for obj in self.detected_objects:
            result += f"  - {obj['name']}: {obj['distance']}cm away at {obj['angle']}°\n"
        return result.strip()
    
    def find_object(self, object_name):
        """Search for a specific object"""
        if not self.camera_active:
            return "Camera is offline. Cannot search."
        
        for obj in self.detected_objects:
            if object_name.lower() in obj['name'].lower():
                return f"Found {obj['name']} at {obj['distance']}cm, angle {obj['angle']}°"
        return f"Object '{object_name}' not found in view."


class NLUEngine:
    """AI-powered Natural Language Understanding — runs 100% offline, no internet needed."""

    INTENTS = {
        "move_left": [
            "move left", "go left", "shift left", "turn left", "swing left",
            "head left", "move the arm left", "slide left", "push left",
            "pan left", "rotate arm left", "go to the left", "left please"
        ],
        "move_right": [
            "move right", "go right", "shift right", "turn right", "swing right",
            "head right", "move the arm right", "slide right", "push right",
            "pan right", "rotate arm right", "go to the right", "right please"
        ],
        "move_up": [
            "move up", "go up", "raise up", "lift up", "go higher", "raise the arm",
            "lift the arm", "arm up", "elevate", "ascend", "reach higher",
            "bring it up", "lift it", "up please"
        ],
        "move_down": [
            "move down", "go down", "lower", "bring down", "drop down",
            "lower the arm", "arm down", "descend", "go lower",
            "bring it down", "lower it", "down please"
        ],
        "move_forward": [
            "move forward", "go forward", "extend forward", "reach forward",
            "advance", "extend the arm", "reach out", "push out", "go ahead",
            "move ahead", "stretch out", "reach further", "push forward"
        ],
        "move_back": [
            "move back", "go back", "retract", "pull back", "go backward",
            "come back", "bring back", "retreat", "draw back", "back up",
            "move backward", "pull in", "go backwards"
        ],
        "move_neutral": [
            "go to neutral", "center the arm", "home position", "reset position",
            "go home", "return to center", "neutral position", "rest position",
            "starting position", "center", "neutral", "home please"
        ],
        "grab": [
            "grab", "pick up", "grasp", "take hold of", "seize", "hold",
            "snatch", "pick it up", "collect it", "fetch", "retrieve",
            "grip it", "catch it", "grab the object", "pick up the item",
            "take the", "get the", "hold the"
        ],
        "release": [
            "release", "drop it", "let go", "put it down", "open the gripper",
            "let it go", "set it down", "place it down", "drop the object",
            "release it", "open hand", "free it", "let loose", "ungrasp",
            "drop", "put down"
        ],
        "camera_on": [
            "turn on the camera", "activate camera", "enable camera", "start camera",
            "camera on", "enable vision", "open your eyes", "turn on vision",
            "activate vision", "start looking", "eyes open", "look with camera"
        ],
        "camera_off": [
            "turn off the camera", "deactivate camera", "disable camera", "stop camera",
            "camera off", "disable vision", "close your eyes", "turn off vision",
            "deactivate vision", "eyes off", "stop looking", "kill camera"
        ],
        "scan": [
            "scan", "look around", "survey", "check surroundings",
            "scan the area", "survey the area", "check the environment",
            "do a scan", "scan environment", "take a look around", "look around you"
        ],
        "list_objects": [
            "what do you see", "show objects", "list objects", "what's there",
            "list items", "show me what's around", "what objects are there",
            "tell me what you see", "show all objects", "what's in the environment",
            "what can you see", "show me the objects", "what items are here"
        ],
        "find_object": [
            "find", "search for", "locate", "where is",
            "look for", "seek", "hunt for", "spot the",
            "find the", "locate the", "where's the", "search for the", "can you find"
        ],
        "add_object": [
            "add object to environment", "register a new object", "put object in workspace",
            "new object in scene", "add item to environment", "register item",
            "introduce new object", "add a new item to the workspace"
        ],
        "remove_object": [
            "remove object", "delete object", "take out", "remove the",
            "delete the", "get rid of", "eliminate object", "erase from environment"
        ],
        "clear_env": [
            "clear environment", "remove all objects", "clean workspace",
            "empty workspace", "clear everything", "reset workspace", "wipe all objects", "clear all"
        ],
        "visualize": [
            "visualize", "show workspace", "display workspace", "show map",
            "show me the layout", "display map", "ascii view", "show the grid",
            "workspace view", "show ascii", "visualize workspace", "show workspace grid"
        ],
        "plot": [
            "plot", "graph", "chart", "show graph", "display graph",
            "plot workspace", "create chart", "show chart", "show plot", "make a graph",
            "create a visualization plot", "matplotlib"
        ],
        "status": [
            "what's your status", "status", "where are you", "arm position",
            "current position", "where is the arm", "system status",
            "what are you doing", "arm status", "position report", "how is the arm",
            "what's the arm position"
        ],
        "help": [
            "help", "what can you do", "commands", "list commands", "instructions",
            "guide me", "what are your features", "how do i use you",
            "show commands", "all commands", "what commands do you have", "command list",
            "what are your abilities"
        ],
        "greeting": [
            "hello", "hi", "hey", "good morning", "good evening", "good afternoon",
            "howdy", "greetings", "sup", "yo", "hi there", "hey there",
            "what's up", "good day"
        ],
        "farewell": [
            "bye", "goodbye", "see you", "farewell", "i'm done",
            "see you later", "take care", "later", "signing off", "bye bye",
            "until next time", "have a good one"
        ],
        "joke": [
            "tell me a joke", "be funny", "make me laugh", "say something funny",
            "humor me", "got any jokes", "tell a joke", "be humorous",
            "make me smile", "entertain me", "crack a joke", "comedy time",
            "say something that will make me laugh"
        ],
        "fun_fact": [
            "tell me something", "teach me something", "fun fact", "share a fact",
            "something interesting", "random fact", "interesting fact",
            "tell me something cool", "share something interesting", "teach me a fact"
        ],
        "web_search": [
            "search for", "search online", "look up online", "google",
            "search the web", "find online", "look it up", "web search",
            "search the internet", "look that up", "find on the web",
        ],
        "learn_fact": [
            "learn that", "remember that", "actually", "that's wrong",
            "the correct answer is", "let me correct you", "teach yourself that",
            "you should know that", "store this fact", "note that"
        ],
        "ask_question": [
            "what is", "who is", "how does", "explain this", "tell me about",
            "what are", "define this", "describe", "what does it mean",
            "can you explain", "tell me about the", "what do you know about"
        ],
        "save": [
            "save", "save data", "remember this state", "store state",
            "save everything", "remember current state", "store everything", "keep this"
        ],
        "load": [
            "load", "recall", "restore", "load data", "retrieve saved data",
            "restore state", "load previous", "reload"
        ],
        "voice_on": [
            "enable voice", "voice on", "speak to me", "voice mode",
            "start speaking", "turn on voice", "activate voice", "talk to me",
            "audio on", "enable speech", "let me hear you", "use your voice"
        ],
        "voice_off": [
            "disable voice", "voice off", "stop speaking", "text mode",
            "silent mode", "turn off voice", "mute", "audio off",
            "disable speech", "stop talking", "be quiet", "go silent"
        ],
        "window_on": [
            "window", "open window", "show window", "avatar window",
            "open avatar", "show avatar", "display window", "nicky window",
            "pop up window", "show the window"
        ],
        "window_off": [
            "close window", "hide window", "close avatar", "hide avatar",
            "shut window", "dismiss window", "remove window"
        ],
        "monitor_on": [
            "monitor on", "screen monitor", "watch my screen", "look at my screen",
            "enable monitor", "start watching", "screen mode on", "enable screen watch",
            "keep an eye on my screen", "monitor mode"
        ],
        "monitor_off": [
            "monitor off", "stop watching", "stop monitoring", "screen mode off",
            "disable monitor", "stop looking at my screen", "close monitor"
        ],
        "screen_look": [
            "what do you see", "describe my screen", "look at this",
            "what's on my screen", "what am i looking at", "check my screen",
            "what's open", "read my screen", "analyze my screen",
            "what can you see", "take a look", "screen check"
        ],
        "proactive_on": [
            "proactive on", "be proactive", "speak up", "talk to me randomly",
            "start talking", "check in on me", "enable proactive", "talk freely"
        ],
        "proactive_off": [
            "proactive off", "stop talking randomly", "be quiet unless asked",
            "disable proactive", "stop checking in", "only talk when spoken to"
        ],
        "place_on": [
            "place on top of", "put on top of", "stack on", "place on",
            "put on", "set on top of", "stack the", "put it on top",
            "place it on", "lay on top of", "stack it on", "balance on top"
        ],
        "thanks": [
            "thank you", "thanks", "appreciate it", "thank you very much",
            "many thanks", "much appreciated", "thanks a lot", "cheers", "ty",
            "that was great thanks", "awesome thanks"
        ],
        "reset": [
            "reset", "restart", "reset system", "start over", "reboot",
            "system reset", "reset everything", "reset the arm", "reset all",
            "start fresh", "clear everything and reset"
        ],
        "how_are_you": [
            "how are you", "how's it going", "how are you doing", "you okay",
            "how do you feel", "are you well", "how's everything", "you alright",
            "everything okay with you", "how's the arm doing"
        ],
        "memory": [
            "show memory", "history", "what have i said", "command history",
            "show history", "past commands", "my history", "conversation history",
            "what did i say", "previous commands", "show my history"
        ],
        "sequence": [
            "run sequence", "execute routine", "play sequence", "run routine",
            "automated routine", "sequence", "routine", "run auto sequence",
            "execute a sequence of moves"
        ],
        "throw": [
            "throw", "toss", "launch", "hurl", "fling", "chuck", "yeet",
            "throw it", "toss it", "launch it", "hurl it", "fling it",
            "throw the", "toss the", "launch the", "chuck it", "throw object",
            "send it flying", "yeet it", "lob it", "lob the"
        ],
        "play_game": [
            "play snake", "play a game", "play game", "start snake", "run snake",
            "play brick breaker", "play brickbreaker", "start brickbreaker",
            "play brick", "launch snake", "launch brickbreaker",
            "play chess", "start chess", "launch chess", "chess game",
            "i want to play a game", "let's play a game", "play a video game",
            "game time", "start a game", "play something",
        ],
    }

    def __init__(self):
        self.model = None
        self._all_examples = []
        self._all_labels = []
        self._vectorizer = None
        self._matrix = None
        self._model_ready = False
        # Load in background — near-instant with sklearn (no torch needed)
        import threading as _t
        _t.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        """Build TF-IDF index over all intent examples. No downloads, no GPU, fast."""
        if not _SKLEARN_OK:
            print("[Nicky AI] sklearn not found — using keyword fallback.")
            print("           Run: pip install scikit-learn  for smarter NLU.")
            return
        try:
            for intent, examples in self.INTENTS.items():
                for ex in examples:
                    self._all_examples.append(ex)
                    self._all_labels.append(intent)
            self._vectorizer = TfidfVectorizer(ngram_range=(1, 3), analyzer="word")
            self._matrix = self._vectorizer.fit_transform(self._all_examples)
            self._model_ready = True
            print("[Nicky AI] ✅ Language model ready!")
        except Exception as e:
            print(f"[Nicky AI] NLU index failed ({e}). Using keyword fallback.")

    def predict(self, text):
        """Returns (intent_name, confidence_score 0-1). Falls back to keywords while model loads."""
        if not self._model_ready or self._vectorizer is None:
            return self._keyword_fallback(text)

        vec = self._vectorizer.transform([text.lower()])
        sims = cosine_similarity(vec, self._matrix).flatten()
        best = int(sims.argmax())
        return self._all_labels[best], float(sims[best])

    def _keyword_fallback(self, text):
        """Simple keyword matching when model isn't available."""
        t = text.lower()
        checks = [
            (["left"],             "move_left"),
            (["right"],            "move_right"),
            (["up", "raise", "lift"], "move_up"),
            (["down", "lower"],    "move_down"),
            (["forward", "ahead"], "move_forward"),
            (["back", "retract"],  "move_back"),
            (["neutral", "center", "home"], "move_neutral"),
            (["grab", "pick", "grasp", "take"], "grab"),
            (["release", "drop", "let go"], "release"),
            (["camera on", "activate camera", "enable camera"], "camera_on"),
            (["camera off", "disable camera"], "camera_off"),
            (["scan", "look around"], "scan"),
            (["what do you see", "list objects", "show objects"], "list_objects"),
            (["find ", "locate ", "where is"], "find_object"),
            (["hello", "hi", "hey"], "greeting"),
            (["bye", "goodbye", "farewell"], "farewell"),
            (["status", "position"], "status"),
            (["help", "commands"], "help"),
            (["visualize", "show workspace"], "visualize"),
            (["plot", "graph", "chart"], "plot"),
            (["joke"], "joke"),
            (["search for", "google ", "look up online", "search online", "search the web"], "web_search"),
            (["learn that", "actually", "remember that"], "learn_fact"),
            (["play snake", "play game", "play brick", "brickbreaker", "game time"], "play_game"),
            (["save"], "save"),
            (["load", "recall"], "load"),
            (["voice on", "enable voice"], "voice_on"),
            (["voice off", "disable voice"], "voice_off"),
            (["window", "open window", "show window"], "window_on"),
            (["close window", "hide window"], "window_off"),
            (["monitor on", "watch my screen", "monitor mode"], "monitor_on"),
            (["monitor off", "stop watching", "stop monitoring"], "monitor_off"),
            (["what do you see", "describe my screen", "look at my screen",
              "what's on my screen", "check my screen", "what am i looking at"], "screen_look"),
            (["proactive on", "be proactive", "speak up", "check in on me"], "proactive_on"),
            (["proactive off", "stop talking randomly", "only talk when spoken to"], "proactive_off"),
            (["thank"], "thanks"),
            (["reset", "restart"], "reset"),
            (["how are you"], "how_are_you"),
            (["history", "memory"], "memory"),
            (["place on", "put on", "stack on"], "place_on"),
            (["clear", "empty"], "clear_env"),
        ]
        for keywords, intent in checks:
            if any(k in t for k in keywords):
                return intent, 0.9
        return "unknown", 0.0
