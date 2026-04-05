import os
import json

try:
    import wikipedia
except ImportError:
    wikipedia = None

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


# Knowledge Base System
class KnowledgeBase:

    # Keyword-based category classifier
    _CATEGORIES = {
        "robotics":    ["robot", "arm", "servo", "motor", "gripper", "sensor", "actuator", "workspace", "degree", "freedom", "robotic"],
        "programming": ["python", "code", "algorithm", "function", "variable", "loop", "class", "api", "software", "script", "debug", "compile", "programming", "coding"],
        "science":     ["physics", "chemistry", "biology", "math", "formula", "equation", "atom", "energy", "force", "quantum", "gravity", "science"],
        "ai":          ["artificial intelligence", "machine learning", "neural", "deep learning", "model", "training", "inference", "llm", "gpt", " ai "],
    }

    # Confidence by source
    _SOURCE_CONFIDENCE = {"user": 1.0, "Wiki": 0.8, "DDG": 0.6, "": 0.9}

    def __init__(self):
        self.facts = {
            "what is python": "Python is a popular programming language used for web development, data science, and automation.",
            "what is ai": "AI (Artificial Intelligence) is technology that enables machines to learn and make decisions.",
            "what is machine learning": "Machine Learning is a subset of AI where computers learn from data without being explicitly programmed.",
            "what is robotics": "Robotics is the field of engineering that deals with design, construction, and operation of robots.",
            "what is a robot": "A robot is a machine designed to automatically carry out a complex series of actions, especially one programmable by a computer.",
            "what is a robotic arm": "A robotic arm is a type of mechanical arm that can perform tasks with precision and is often used in manufacturing and research.",
            "who are you": "I am Nicky, your robotic arm assistant AI.",
            "who made you": "I was created by Moofun.",
            "who created you": "I was created by Moofun.",
            "who is your creator": "My creator is Moofun.",
            "who built you": "I was built by Moofun.",
            "what can you do": "I can control robotic arms, see with cameras, understand multiple objects, and have intelligent conversations.",
            "how do robots work": "Robots use sensors to perceive their environment, processors to make decisions, and actuators to move.",
            "what is an algorithm": "An algorithm is a step-by-step procedure for solving a problem or accomplishing a task.",
            "what is automation": "Automation is using technology to perform tasks with minimal human intervention.",
            "what is 1x1": "1 times 1 equals 1. Any number multiplied by 1 stays the same.",
            "what is 2x2": "2 times 2 equals 4.",
            "what is programming": "Programming is the process of creating a set of instructions that tell a computer how to perform a task.",
            "what is coding": "Coding is the practice of writing code in a programming language to create software and applications.",
        }
    
    def lookup(self, question):
        """Look up a question in the knowledge base"""
        question_lower = question.lower().strip()
        for key, value in self.facts.items():
            if key in question_lower or question_lower in key:
                return self._fact_answer(value)
        return None

    # ── Fact accessor helpers (support both old str and new dict format) ──

    def _fact_answer(self, val):
        return val.get("answer", "") if isinstance(val, dict) else (val or "")

    def _fact_confidence(self, val):
        return val.get("confidence", 1.0) if isinstance(val, dict) else 1.0

    def _fact_category(self, val):
        return val.get("category", "general") if isinstance(val, dict) else "general"

    def _categorize(self, key, answer):
        """Classify a fact into a category based on keywords."""
        text = (key + " " + answer).lower()
        for cat, keywords in self._CATEGORIES.items():
            if any(kw in text for kw in keywords):
                return cat
        return "general"
    
    def search_wikipedia(self, query):
        """Search Wikipedia for an answer"""
        if wikipedia is None:
            return None
        try:
            result = wikipedia.summary(query, sentences=2)
            return result
        except Exception:
            return None

    def search_duckduckgo(self, query):
        """Search DuckDuckGo, filtering junk and trimming to complete sentences."""
        if DDGS is None:
            return None
        try:
            results = list(DDGS().text(query, max_results=5))
            noise = ("reddit.com", "quora.com", "twitter.com", "facebook.com",
                     "youtube.com", "tiktok.com", "forum", "· ")
            for r in results:
                body = r.get("body", "").strip()
                url  = r.get("href", "")
                if not body or len(body) < 40:
                    continue
                if any(n in url or n in body for n in noise):
                    continue
                return self._trim_to_sentences(body, max_sentences=3)
            # Fall back to first result, still trimmed
            if results:
                return self._trim_to_sentences(results[0].get("body", ""), max_sentences=3)
        except Exception as e:
            print(f"[Nicky] Warning: DuckDuckGo search failed: {e}")
        return None

    @staticmethod
    def _trim_to_sentences(text, max_sentences=3):
        """Return up to max_sentences complete sentences from text."""
        import re
        text = text.strip()
        # Remove date prefixes like "Oct 21, 2023 · "
        text = re.sub(r'^[A-Z][a-z]{2} \d{1,2}, \d{4}\s*[·•]\s*', '', text)
        # Split on sentence endings
        sentences = re.split(r'(?<=[.!?])\s+', text)
        # Drop any sentence that ends with ... or is incomplete
        complete = [s for s in sentences if s and not s.rstrip().endswith(('…', '...'))]
        if not complete:
            # Last resort: just cut at last full stop
            last = text.rfind('.')
            return text[:last + 1] if last != -1 else text
        return ' '.join(complete[:max_sentences])

    def answer_question(self, question):
        """Try to answer using: knowledge base → DuckDuckGo → Wikipedia. Auto-saves new findings."""
        # 1. Local knowledge base — return highest-confidence answer if multiple matches
        matches = []
        q_lower = question.lower().strip()
        for key, val in self.facts.items():
            if key in q_lower or q_lower in key:
                matches.append((self._fact_confidence(val), self._fact_answer(val)))
        if matches:
            matches.sort(reverse=True)
            return matches[0][1]

        # 2. DuckDuckGo
        answer = self.search_duckduckgo(question)
        if answer:
            self._auto_store(question, answer, source="DDG")
            return answer

        # 3. Wikipedia
        answer = self.search_wikipedia(question)
        if answer:
            self._auto_store(question, answer, source="Wiki")
            return answer

        return None

    def _normalize_key(self, text):
        """Strip filler words to create a clean storage key."""
        import re
        key = text.lower().strip().rstrip("?.!")
        for prefix in ("what is ", "what are ", "who is ", "who was ",
                       "tell me about ", "explain ", "describe ",
                       "how does ", "how do ", "why is ", "why does "):
            if key.startswith(prefix):
                key = key[len(prefix):]
                break
        return re.sub(r'\s+', ' ', key).strip()

    def _auto_store(self, question, answer, source=""):
        """Save a learned fact from search into the persistent knowledge base with metadata."""
        key = self._normalize_key(question)
        if not key:
            return
        # Don't overwrite a higher-confidence existing fact
        existing = self.facts.get(key)
        if existing:
            existing_conf = self._fact_confidence(existing)
            new_conf = self._SOURCE_CONFIDENCE.get(source, 0.6)
            if existing_conf >= new_conf:
                return
        confidence = self._SOURCE_CONFIDENCE.get(source, 0.6)
        category = self._categorize(key, answer)
        fact_entry = {"answer": answer, "source": source, "confidence": confidence, "category": category}
        self.facts[key] = fact_entry
        full_key = question.lower().strip().rstrip("?.!")
        if full_key != key:
            self.facts[full_key] = fact_entry
        if source:
            print(f"[Nicky] 🧠 Stored from {source} [{category}]: \"{key}\"")
        self._persist()

    def _persist(self):
        """Write facts to disk immediately after learning."""
        try:
            path = os.path.join("nicky_data", "knowledge_base.json")
            os.makedirs("nicky_data", exist_ok=True)
            with open(path, "w") as f:
                json.dump(self.facts, f, indent=2)
        except Exception as e:
            print(f"[Nicky] Warning: could not persist knowledge base: {e}")

    def load_from_disk(self):
        """Load previously saved facts from disk into memory."""
        try:
            path = os.path.join("nicky_data", "knowledge_base.json")
            if os.path.exists(path):
                with open(path) as f:
                    saved = json.load(f)
                self.facts.update(saved)
        except Exception:
            pass

    def learn_fact(self, question, answer):
        """Learn a new fact, checking for contradictions first."""
        question_lower = question.lower().strip()
        conflict = self._check_contradiction(question_lower, answer)
        if conflict:
            return f"⚠️ I already know something different about that: \"{conflict}\". Say 'override: {question}' to update it."
        category = self._categorize(question_lower, answer)
        self.facts[question_lower] = {"answer": answer, "source": "user", "confidence": 1.0, "category": category}
        self._persist()
        return f"Learned: {question_lower} -> {answer}"

    def override_fact(self, question, answer):
        """Force-overwrite a fact even if a contradiction exists."""
        key = question.lower().strip()
        category = self._categorize(key, answer)
        self.facts[key] = {"answer": answer, "source": "user", "confidence": 1.0, "category": category}
        self._persist()
        return f"Updated: {key} -> {answer}"

    def _check_contradiction(self, key, new_value):
        """Return existing value if it meaningfully differs from new_value, else None."""
        existing = self.facts.get(key, "")
        if not existing:
            return None
        existing_str = self._fact_answer(existing)
        if existing_str.strip().lower() != new_value.strip().lower():
            return existing_str
        return None

    def find_relevant(self, query, max_facts=4):
        """Return up to max_facts (key, value) pairs whose keys overlap with query keywords."""
        import re
        stop = {"what","is","are","was","the","a","an","of","in","on","at","to","do",
                "how","why","who","when","does","did","can","tell","me","about","and"}
        words = {w for w in re.findall(r"[a-z]+", query.lower()) if w not in stop and len(w) > 2}
        if not words:
            return []
        scored = []
        for k, v in self.facts.items():
            k_words = set(re.findall(r"[a-z]+", k.lower()))
            overlap = len(words & k_words)
            if overlap:
                # Boost score by confidence
                conf = self._fact_confidence(v)
                scored.append((overlap * conf, k, self._fact_answer(v)))
        scored.sort(reverse=True)
        return [(k, v) for _, k, v in scored[:max_facts]]


class UserMemory:
    """Remembers facts about the user across sessions."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.facts = {}   # e.g. {"name": "Elias", "likes": ["jazz", "coding"]}
        self._load()

    def _load(self):
        path = os.path.join(self.data_dir, "user_memory.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.facts = json.load(f)
            except Exception:
                self.facts = {}

    def save(self):
        path = os.path.join(self.data_dir, "user_memory.json")
        try:
            with open(path, "w") as f:
                json.dump(self.facts, f, indent=2)
        except Exception:
            pass

    def learn(self, key, value):
        """Store or update a fact about the user."""
        if isinstance(value, list):
            existing = self.facts.get(key, [])
            if not isinstance(existing, list):
                existing = [existing]
            if value[0] not in existing:
                existing.extend(value)
            self.facts[key] = existing
        else:
            self.facts[key] = value
        self.save()

    def extract_from_text(self, text):
        """Auto-detect personal facts from what the user says."""
        import re
        t = text.lower()
        found = {}

        # "my name is X"
        m = re.search(r"my name is ([a-z]+)", t, re.IGNORECASE)
        if m:
            found["name"] = m.group(1).capitalize()

        # "i am X" / "i'm X" (job/description)
        m = re.search(r"i(?:'m| am) (?:a |an )?([a-z]+ ?[a-z]*)", t, re.IGNORECASE)
        if m and m.group(1) not in ("fine", "good", "okay", "ok", "here", "back", "not",
                                    "going", "trying", "just", "also", "still", "really"):
            found["description"] = m.group(1).strip()

        # "i'm building X" / "i'm working on X" / "my project is X"
        m = re.search(r"(?:i(?:'m| am) (?:building|working on|creating|making)|my project is) ([a-z][\w ]{2,40})", t, re.IGNORECASE)
        if m:
            found["project"] = m.group(1).strip()

        # "i like/love X"
        m = re.search(r"i (?:like|love|enjoy|prefer) ([a-z][\w ]{2,30})", t, re.IGNORECASE)
        if m:
            found["likes"] = [m.group(1).strip()]

        # "i hate/dislike X"
        m = re.search(r"i (?:hate|dislike|don't like|cant stand) ([a-z][\w ]{2,30})", t, re.IGNORECASE)
        if m:
            found["dislikes"] = [m.group(1).strip()]

        # "i play X" / "my hobby is X"
        m = re.search(r"(?:i play|my hobby is|i spend time) ([a-z][\w ]{2,30})", t, re.IGNORECASE)
        if m:
            found.setdefault("hobbies", []).append(m.group(1).strip())

        # "my favourite X is Y" / "my favorite X is Y"
        m = re.search(r"my favou?rite ([a-z]+) is ([a-z][\w ]{1,30})", t, re.IGNORECASE)
        if m:
            found[f"favourite_{m.group(1).strip()}"] = m.group(2).strip()

        # "i have a test / meeting / deadline / appointment [on/tomorrow/...]"
        m = re.search(r"i have (?:a |an )?(test|exam|meeting|deadline|appointment|interview|presentation)([\w\s]{0,30})", t, re.IGNORECASE)
        if m:
            self._add_note(f"{m.group(1)}{m.group(2).rstrip()}")

        # "i need to X" / "i have to X" — save as a note
        m = re.search(r"i (?:need to|have to|must|should) ([a-z][\w ]{3,40})", t, re.IGNORECASE)
        if m and not any(skip in m.group(1) for skip in ("say", "ask", "tell", "know", "find")):
            self._add_note(f"needs to {m.group(1).strip()}")

        # Named people: "my friend X" / "my brother X" etc.
        m = re.search(r"my (friend|brother|sister|mum|mom|dad|father|mother|boyfriend|girlfriend|partner|boss|teacher|colleague) ([A-Z][a-z]+)", text)
        if m:
            rel, name = m.group(1), m.group(2)
            people = self.facts.get("people", {})
            people[name] = rel
            found["people"] = people

        for key, value in found.items():
            self.learn(key, value)

        return found

    def _add_note(self, note: str):
        """Add a short-term note (capped at 10)."""
        notes = self.facts.get("notes", [])
        if note not in notes:
            notes.append(note)
        self.facts["notes"] = notes[-10:]
        self.save()

    def summarise(self) -> str:
        """Return a human-readable summary of everything stored."""
        if not self.facts:
            return "I don't know much about you yet — tell me something!"
        lines = []
        if "name" in self.facts:
            lines.append(f"👤 Name: {self.facts['name']}")
        if "description" in self.facts:
            lines.append(f"🏷️  You described yourself as: {self.facts['description']}")
        if "project" in self.facts:
            lines.append(f"🛠️  Project: {self.facts['project']}")
        if "likes" in self.facts:
            lines.append(f"❤️  Likes: {', '.join(self.facts['likes'])}")
        if "dislikes" in self.facts:
            lines.append(f"👎 Dislikes: {', '.join(self.facts['dislikes'])}")
        if "hobbies" in self.facts:
            lines.append(f"🎮 Hobbies: {', '.join(self.facts['hobbies'])}")
        if "notes" in self.facts and self.facts["notes"]:
            lines.append(f"📌 Notes: {'; '.join(self.facts['notes'])}")
        if "people" in self.facts:
            ppl = ", ".join(f"{n} ({r})" for n, r in self.facts["people"].items())
            lines.append(f"👥 People you've mentioned: {ppl}")
        for key, val in self.facts.items():
            if key.startswith("favourite_"):
                label = key.replace("favourite_", "").capitalize()
                lines.append(f"⭐ Favourite {label}: {val}")
        for key, val in self.facts.items():
            if key not in ("name", "description", "project", "likes", "dislikes",
                           "hobbies", "notes", "people") and not key.startswith("favourite_"):
                lines.append(f"  • {key}: {val}")
        return "\n".join(lines)

    def as_prompt_text(self):
        """Return a string summarising what Nicky knows about the user."""
        if not self.facts:
            return ""
        parts = []
        if "name" in self.facts:
            parts.append(f"The user's name is {self.facts['name']}.")
        if "description" in self.facts:
            parts.append(f"They described themselves as: {self.facts['description']}.")
        if "project" in self.facts:
            parts.append(f"They are working on: {self.facts['project']}.")
        if "likes" in self.facts:
            parts.append(f"They like: {', '.join(self.facts['likes'])}.")
        if "dislikes" in self.facts:
            parts.append(f"They dislike: {', '.join(self.facts['dislikes'])}.")
        if "hobbies" in self.facts:
            parts.append(f"Their hobbies include: {', '.join(self.facts['hobbies'])}.")
        if "notes" in self.facts and self.facts["notes"]:
            parts.append(f"Recent notes about them: {'; '.join(self.facts['notes'])}.")
        if "people" in self.facts:
            ppl = ", ".join(f"{n} ({r})" for n, r in self.facts["people"].items())
            parts.append(f"People they've mentioned: {ppl}.")
        for key, val in self.facts.items():
            if key.startswith("favourite_"):
                label = key.replace("favourite_", "")
                parts.append(f"Their favourite {label} is {val}.")
        for key, val in self.facts.items():
            if key not in ("name", "description", "project", "likes", "dislikes",
                           "hobbies", "notes", "people") and not key.startswith("favourite_"):
                parts.append(f"{key}: {val}.")
        return "What you know about the user — " + " ".join(parts)
