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
    def __init__(self):
        self.facts = {
            "what is python": "Python is a popular programming language used for web development, data science, and automation.",
            "what is ai": "AI (Artificial Intelligence) is technology that enables machines to learn and make decisions.",
            "what is machine learning": "Machine Learning is a subset of AI where computers learn from data without being explicitly programmed.",
            "what is robotics": "Robotics is the field of engineering that deals with design, construction, and operation of robots.",
            "what is a robot": "A robot is a machine designed to automatically carry out a complex series of actions, especially one programmable by a computer.",
            "what is a robotic arm": "A robotic arm is a type of mechanical arm that can perform tasks with precision and is often used in manufacturing and research.",
            "who are you": "I am Nicky, your robotic arm assistant AI.",
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
                return value
        return None
    
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
        # 1. Local knowledge base
        answer = self.lookup(question)
        if answer:
            return answer

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
        """Save a learned fact from search into the persistent knowledge base."""
        key = self._normalize_key(question)
        if not key or key in self.facts:
            return  # already known — don't overwrite manual facts
        self.facts[key] = answer
        # Also store under the full question form for wider matching
        full_key = question.lower().strip().rstrip("?.!")
        if full_key != key:
            self.facts[full_key] = answer
        if source:
            print(f"[Nicky] 🧠 Stored from {source}: \"{key}\"")
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
        self.facts[question_lower] = answer
        self._persist()
        return f"Learned: {question_lower} -> {answer}"

    def override_fact(self, question, answer):
        """Force-overwrite a fact even if a contradiction exists."""
        key = question.lower().strip()
        self.facts[key] = answer
        self._persist()
        return f"Updated: {key} -> {answer}"

    def _check_contradiction(self, key, new_value):
        """Return existing value if it meaningfully differs from new_value, else None."""
        existing = self.facts.get(key, "")
        if not existing:
            return None
        # Consider it a contradiction if the values differ beyond trivial whitespace/case
        if existing.strip().lower() != new_value.strip().lower():
            return existing
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
                scored.append((overlap, k, v))
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

        # "i am X years old"
        m = re.search(r"i(?:'m| am) (\d+)(?: years old)?", t, re.IGNORECASE)
        if m:
            found["age"] = m.group(1)

        # "i live in X" / "i'm from X" / "i'm in X"
        m = re.search(r"i(?:'m| am) (?:from|in) ([a-z][\w ]{2,25})", t, re.IGNORECASE)
        if not m:
            m = re.search(r"i live in ([a-z][\w ]{2,25})", t, re.IGNORECASE)
        if m:
            found["location"] = m.group(1).strip().title()

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

        for key, value in found.items():
            self.learn(key, value)

        return found

    def as_prompt_text(self):
        """Return a string summarising what Nicky knows about the user."""
        if not self.facts:
            return ""
        parts = []
        if "name" in self.facts:
            parts.append(f"The user's name is {self.facts['name']}.")
        if "age" in self.facts:
            parts.append(f"They are {self.facts['age']} years old.")
        if "location" in self.facts:
            parts.append(f"They are from/in {self.facts['location']}.")
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
        for key, val in self.facts.items():
            if key not in ("name", "age", "location", "description", "project", "likes", "dislikes", "hobbies"):
                parts.append(f"{key}: {val}.")
        return "What you know about the user — " + " ".join(parts)
