import os
import json


# Personality System - Adds emotions and dynamic responses
class PersonalitySystem:
    def __init__(self):
        self.mood = "neutral"  # neutral, happy, curious, focused
        self.interaction_count = 0
        self.moods_cycle = ["neutral", "happy", "curious", "focused"]
    
    def update_mood(self):
        """Update mood based on interactions"""
        self.interaction_count += 1
        self.mood = self.moods_cycle[self.interaction_count % len(self.moods_cycle)]
    
    def get_greeting(self):
        """Return greeting based on mood"""
        greetings = {
            "neutral": "Hello. How can I assist you?",
            "happy": "Great to see you! What can I do for you?",
            "curious": "I'm interested in what you have to say. Tell me more!",
            "focused": "Analyzing your request. What do you need?"
        }
        return greetings.get(self.mood, "Hello!")
    
    def get_response_prefix(self):
        """Add personality to responses"""
        prefixes = {
            "neutral": "",
            "happy": "Wonderful! ",
            "curious": "Interesting... ",
            "focused": "Understood. "
        }
        return prefixes.get(self.mood, "")


class CustomPersonality:
    """Lets the user shape Nicky's personality through conversation."""

    TRAIT_TRIGGERS = {
        "sarcastic":  ["be more sarcastic", "be sarcastic", "act sarcastic"],
        "funny":      ["be more funny", "be funnier", "be funny", "make me laugh more"],
        "serious":    ["be more serious", "be serious", "stop joking", "act professional"],
        "casual":     ["be more casual", "be casual", "relax a bit", "chill out"],
        "energetic":  ["be more energetic", "be enthusiastic", "be excited"],
        "concise":    ["be more concise", "keep it short", "shorter answers", "be brief"],
        "detailed":   ["be more detailed", "give more detail", "elaborate more", "explain more"],
    }

    TRAIT_DESCRIPTIONS = {
        "sarcastic":  "You are slightly sarcastic and witty, but still helpful.",
        "funny":      "You inject humour and light jokes into responses when appropriate.",
        "serious":    "You are professional and to-the-point, minimal jokes.",
        "casual":     "You speak casually, like talking to a friend.",
        "energetic":  "You are upbeat and enthusiastic in everything you say.",
        "concise":    "You keep all responses as short as possible — one or two sentences max.",
        "detailed":   "You give thorough, detailed explanations when answering.",
    }

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.traits = []
        self._load()

    def _load(self):
        path = os.path.join(self.data_dir, "personality.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.traits = json.load(f)
            except Exception:
                self.traits = []

    def save(self):
        path = os.path.join(self.data_dir, "personality.json")
        try:
            with open(path, "w") as f:
                json.dump(self.traits, f, indent=2)
        except Exception:
            pass

    def detect_and_apply(self, text):
        """Check if the user is asking to change personality. Returns response or None."""
        t = text.lower()
        for trait, triggers in self.TRAIT_TRIGGERS.items():
            if any(trigger in t for trigger in triggers):
                if trait not in self.traits:
                    self.traits.append(trait)
                else:
                    self.traits.remove(trait)
                    self.save()
                    return f"Okay, toning down the {trait} side."
                self.save()
                return f"Got it — I'll be more {trait} from now on."
        if any(p in t for p in ("reset personality", "default personality", "stop being", "normal please")):
            self.traits = []
            self.save()
            return "Personality reset to default."
        return None

    def as_prompt_text(self):
        """Return active trait instructions for the system prompt."""
        if not self.traits:
            return ""
        descriptions = [self.TRAIT_DESCRIPTIONS[t] for t in self.traits if t in self.TRAIT_DESCRIPTIONS]
        return "Active personality traits: " + " ".join(descriptions)
