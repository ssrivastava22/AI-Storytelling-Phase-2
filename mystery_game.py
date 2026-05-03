from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import json
import os
import re
import urllib.error
import urllib.request


# -----------------------------
# Data Models
# -----------------------------

@dataclass
class Room:
    name: str
    description: str
    exits: Dict[str, str] = field(default_factory=dict)


@dataclass
class Item:
    name: str
    description: str
    location: str
    destroyed: bool = False
    collected: bool = False


@dataclass
class NPC:
    name: str
    description: str
    location: str
    alive: bool = True


@dataclass
class PlotBeat:
    id: int
    title: str
    location: str
    required_items: List[str]
    required_npcs: List[str]
    clue_unlocked: str
    summary: str
    completed: bool = False
    invalidated: bool = False


@dataclass
class WorldState:
    current_location: str
    inventory: Set[str] = field(default_factory=set)
    discovered_clues: Set[str] = field(default_factory=set)
    flags: Dict[str, bool] = field(default_factory=dict)


# -----------------------------
# Fixed Story-to-World Mapping
# -----------------------------

def generate_world():
    rooms = {
        "botanical garden": Room(
            "botanical garden",
            "You stand in the museum's botanical garden, where Evelyn Harper was poisoned. Rare toxic plants line the paths."
        ),
        "garden shed": Room(
            "garden shed",
            "A cramped shed filled with gardening tools, soil bags, and locked cabinets."
        ),
        "museum hall": Room(
            "museum hall",
            "The central hall of Harper & Sons Museum. Displays cast long shadows across the marble floor."
        ),
        "office": Room(
            "office",
            "Evelyn Harper's office. Financial records, drawers, and filing cabinets fill the room."
        ),
        "thomas office": Room(
            "thomas office",
            "Thomas Blake's office. It is neat, expensive, and suspiciously controlled."
        ),
        "coast": Room(
            "coast",
            "A secluded coastal overlook where secret meetings can happen away from the museum."
        ),
    }

    rooms["botanical garden"].exits = {"shed": "garden shed", "hall": "museum hall"}
    rooms["garden shed"].exits = {"garden": "botanical garden"}
    rooms["museum hall"].exits = {"garden": "botanical garden", "office": "office", "thomas": "thomas office", "coast": "coast"}
    rooms["office"].exits = {"hall": "museum hall"}
    rooms["thomas office"].exits = {"hall": "museum hall"}
    rooms["coast"].exits = {"hall": "museum hall"}

    items = {
        "vial": Item("vial", "A vial of dark liquid hidden in the garden shed.", "garden shed"),
        "business card": Item("business card", "A torn business card belonging to Thomas Blake.", "garden shed"),
        "ledger": Item("ledger", "A ledger showing suspicious withdrawals.", "office"),
        "key": Item("key", "A key from Thomas's office.", "thomas office"),
        "drawer documents": Item("drawer documents", "Documents revealing unauthorized funds tied to Thomas.", "office"),
        "footprint": Item("footprint", "A footprint outside the garden shed matching Gregory's presence.", "botanical garden"),
        "crumpled paper": Item("crumpled paper", "A paper mentioning a backup plan if Evelyn's exhibit failed.", "botanical garden"),
        "burnt memo": Item("burnt memo", "A half-burnt memo saying: 'Ensure no witnesses' next to Evelyn's name.", "museum hall"),
    }

    npcs = {
        "linda": NPC("linda", "Linda Harper, Evelyn's estranged sister.", "museum hall"),
        "gregory": NPC("gregory", "Gregory Wells, the museum security guard.", "museum hall"),
        "thomas": NPC("thomas", "Thomas Blake, Evelyn's professional rival.", "thomas office"),
    }

    story_plan = [
        PlotBeat(1, "Find poison evidence", "garden shed", ["vial", "business card"], [], "poison evidence",
                 "You find a vial and Thomas's torn business card, linking him to the poison."),
        PlotBeat(2, "Overhear Linda and Gregory", "museum hall", [], ["linda", "gregory"], "secret conversation",
                 "You overhear Linda and Gregory whispering about Thomas's wrath."),
        PlotBeat(3, "Confront Linda", "museum hall", [], ["linda"], "linda motive",
                 "Linda reveals resentment toward Evelyn's success."),
        PlotBeat(4, "Investigate financial records", "office", ["ledger"], [], "suspicious withdrawals",
                 "The ledger shows suspicious withdrawals near the failed charity event."),
        PlotBeat(5, "Verify bank records", "office", ["ledger"], [], "thomas signatures",
                 "A bank contact confirms the withdrawals were signed by Thomas."),
        PlotBeat(6, "Follow Gregory", "coast", [], ["gregory", "linda"], "embezzlement document",
                 "You follow Gregory and overhear him meeting Linda about the embezzlement."),
        PlotBeat(7, "Confront Thomas", "thomas office", [], ["thomas"], "contradicted alibi",
                 "Thomas gives an alibi, but a timestamped email contradicts him."),
        PlotBeat(8, "Find key", "thomas office", ["key"], [], "drawer key",
                 "You find a key that may open the locked drawer in Evelyn's office."),
        PlotBeat(9, "Open locked drawer", "office", ["key", "drawer documents"], [], "unauthorized funds",
                 "The drawer reveals unauthorized funds tied to Thomas."),
        PlotBeat(10, "Find Gregory footprint", "botanical garden", ["footprint"], [], "gregory crime scene link",
                 "A footprint places Gregory at the crime scene."),
        PlotBeat(11, "Find backup plan", "botanical garden", ["crumpled paper"], [], "backup plan",
                 "A crumpled paper reveals Thomas's calculated backup plan."),
        PlotBeat(12, "Find final memo", "museum hall", ["burnt memo"], [], "ensure no witnesses memo",
                 "The burnt memo proves the plan included eliminating witnesses."),
        PlotBeat(13, "Final accusation", "museum hall", [], ["thomas", "gregory"], "final reveal",
                 "You confront Thomas and Gregory with the evidence as police arrive."),
    ]

    world = WorldState(current_location="botanical garden")
    world.flags["coast_meeting_scheduled"] = False
    world.flags["final_confrontation_ready"] = False
    return rooms, items, npcs, story_plan, world


# -----------------------------
# Action Interpreter / Parser
# -----------------------------

def interpret_action_rules(text: str):
    text = text.lower().strip()

    if text in ["quit", "exit"]:
        return {"type": "quit"}

    if text.startswith("go "):
        return {"type": "move", "target": text.replace("go ", "").strip()}

    if text.startswith("move "):
        return {"type": "move", "target": text.replace("move ", "").strip()}

    if any(word in text for word in ["look", "inspect room", "where am i"]):
        return {"type": "look"}

    if any(word in text for word in ["take", "pick up", "grab", "collect"]):
        return {"type": "take", "target": extract_target(text)}

    if any(word in text for word in ["examine", "inspect", "search", "read"]):
        return {"type": "examine", "target": extract_target(text)}

    if any(word in text for word in ["talk", "ask", "interview", "confront"]):
        return {"type": "talk", "target": extract_target(text)}

    if any(word in text for word in ["destroy", "burn", "break", "throw away", "hide", "kill", "lock"]):
        return {"type": "exception_attempt", "target": extract_target(text)}

    return {"type": "other", "raw": text}


def extract_target(text: str):
    known = [
        "vial", "business card", "ledger", "key", "drawer documents",
        "footprint", "crumpled paper", "burnt memo",
        "linda", "gregory", "thomas", "drawer", "shed", "office"
    ]
    for k in known:
        if k in text:
            return k
    return text


class ActionInterpreter:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.llm_enabled = bool(self.openai_api_key)

    def interpret(self, text: str):
        if self.llm_enabled:
            action = self._interpret_with_llm(text)
            if action:
                return action
        return interpret_action_rules(text)

    def _interpret_with_llm(self, text: str):
        prompt = (
            "Convert this player input into a game action JSON.\n"
            "Allowed action types: quit, move, look, take, examine, talk, exception_attempt, other.\n"
            'Output strict JSON object only: {"type":"...", "target":"..."}.\n'
            "Include target only when relevant."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
        }

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"].strip()
            action = json.loads(content)
            if not isinstance(action, dict) or "type" not in action:
                return None
            return action
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError):
            return None


# -----------------------------
# Game Engine
# -----------------------------

class MysteryGame:
    def __init__(self):
        self.rooms, self.items, self.npcs, self.story_plan, self.world = generate_world()
        self.interpreter = ActionInterpreter()
        self.debug_log = []
        parser_mode = "LLM parser" if self.interpreter.llm_enabled else "Rule parser (LLM fallback disabled)"
        self.log(f"Parser Mode: {parser_mode}")

    def log(self, message):
        self.debug_log.append(message)

    def current_room(self):
        return self.rooms[self.world.current_location]

    def describe_location(self):
        room = self.current_room()
        visible_items = [
            item.name for item in self.items.values()
            if item.location == room.name and not item.destroyed and not item.collected
        ]
        visible_npcs = [
            npc.name for npc in self.npcs.values()
            if npc.location == room.name and npc.alive
        ]

        output = f"\n📍 {room.name.title()}\n{room.description}\n"
        if visible_items:
            output += f"Items here: {', '.join(visible_items)}\n"
        if visible_npcs:
            output += f"People here: {', '.join(visible_npcs)}\n"
        output += f"Exits: {', '.join(room.exits.keys())}\n"
        return output

    def normalize_target(self, action_type: str, raw_target):
        if not isinstance(raw_target, str):
            return raw_target

        target = raw_target.lower().strip()
        target = re.sub(r"[^a-z0-9\s]", " ", target)
        target = re.sub(r"\s+", " ", target).strip()

        # Strip common filler prefixes from natural language commands.
        prefixes = ["back to ", "go to ", "move to ", "to the ", "to ", "the ", "a ", "an ", "at ", "in "]
        changed = True
        while changed:
            changed = False
            for prefix in prefixes:
                if target.startswith(prefix):
                    target = target[len(prefix):].strip()
                    changed = True

        aliases = {
            "footprints": "footprint",
            "print": "footprint",
            "memo": "burnt memo",
            "burnt note": "burnt memo",
            "note": "crumpled paper",
            "paper": "crumpled paper",
            "docs": "drawer documents",
            "documents": "drawer documents",
            "drawers": "drawer",
            "hallway": "hall",
            "museum": "museum hall",
            "thomas's office": "thomas office",
            "thomas office": "thomas office",
        }
        if target in aliases:
            return aliases[target]

        if action_type == "move":
            room = self.current_room()
            valid_moves = set(room.exits.keys()) | set(room.exits.values())
            if target in valid_moves:
                return target
            for candidate in valid_moves:
                if candidate in target:
                    return candidate
            if target.endswith("s") and target[:-1] in valid_moves:
                return target[:-1]
            return target

        valid_targets = set(self.items.keys()) | set(self.npcs.keys()) | {"drawer"}
        if target in valid_targets:
            return target
        if target.endswith("s") and target[:-1] in valid_targets:
            return target[:-1]
        for candidate in valid_targets:
            if candidate in target:
                return candidate
        return target

    def apply_action(self, action):
        action_type = action["type"]
        if "target" in action:
            action["target"] = self.normalize_target(action_type, action["target"])

        if action_type == "quit":
            return "quit"

        if action_type == "look":
            return self.describe_location()

        if action_type == "move":
            if "target" not in action or not str(action["target"]).strip():
                return "Where do you want to go?"
            return self.move(action["target"])

        if action_type == "take":
            if "target" not in action or not str(action["target"]).strip():
                return "What do you want to take?"
            return self.take_item(action["target"])

        if action_type == "examine":
            if "target" not in action or not str(action["target"]).strip():
                return "What do you want to examine?"
            return self.examine(action["target"])

        if action_type == "talk":
            if "target" not in action or not str(action["target"]).strip():
                return "Who do you want to talk to?"
            return self.talk(action["target"])

        if action_type == "exception_attempt":
            if "target" not in action or not str(action["target"]).strip():
                return "What are you trying to alter?"
            return self.handle_exception(action["target"])

        return "You try that, but it does not meaningfully change the investigation."

    def move(self, direction):
        room = self.current_room()
        if direction in room.exits:
            destination = room.exits[direction]
        else:
            destination = ""
            for exit_key, exit_room in room.exits.items():
                if direction == exit_room or direction == exit_key:
                    destination = exit_room
                    break
        if destination:
            self.world.current_location = destination
            self.log(f"World State Updated: player moved to {self.world.current_location}")
            story_result = self.evaluate_story()
            location_desc = self.describe_location()
            return location_desc + (f"\n{story_result}" if story_result else "")
        return "You cannot go that way."

    def take_item(self, target):
        if target not in self.items:
            return "You do not see that here."

        item = self.items[target]
        if item.location != self.world.current_location or item.destroyed:
            return "That item is not available here."

        item.collected = True
        self.world.inventory.add(target)
        self.log(f"World State Updated: player collected {target}")
        story_result = self.evaluate_story()
        return f"You collect the {target}." + (f"\n{story_result}" if story_result else "")

    def examine(self, target):
        if target in self.items:
            item = self.items[target]

            if item.destroyed:
                return f"The {target} has been destroyed."

            if item.location == self.world.current_location or target in self.world.inventory:
                self.world.discovered_clues.add(target)
                self.log(f"Clue Discovered: {target}")
                story_result = self.evaluate_story()
                return f"{item.description}\n{story_result}"

        if target == "drawer":
            if "key" in self.world.inventory:
                self.world.discovered_clues.add("drawer documents")
                self.items["drawer documents"].collected = True
                self.world.inventory.add("drawer documents")
                self.log("Clue Discovered: drawer documents")
                story_result = self.evaluate_story()
                return "You unlock the drawer and find documents revealing unauthorized funds tied to Thomas.\n" + story_result
            return "The drawer is locked. You need a key."

        return "You find nothing useful."

    def talk(self, target):
        if target not in self.npcs:
            return "That person is not here."

        npc = self.npcs[target]
        if npc.location != self.world.current_location or not npc.alive:
            return f"{target.title()} is not available here."

        self.world.discovered_clues.add(f"talked to {target}")
        self.log(f"NPC Interaction: talked to {target}")

        if target == "linda":
            self.world.discovered_clues.add("linda motive")
            return "Linda avoids your questions at first, but her jealousy of Evelyn becomes obvious.\n" + self.evaluate_story()

        if target == "gregory":
            self.world.discovered_clues.add("gregory suspicious")
            return "Gregory stays calm, but his answers are too polished. Something feels rehearsed.\n" + self.evaluate_story()

        if target == "thomas":
            self.world.discovered_clues.add("contradicted alibi")
            return "Thomas insists he was at dinner, but his timeline does not quite hold.\n" + self.evaluate_story()

        return "They have little to say."

    # -----------------------------
    # Drama Manager: Evaluate Story
    # -----------------------------

    def evaluate_story(self):
        self.update_dynamic_world()
        advanced = []

        for beat in self.story_plan:
            if beat.completed or beat.invalidated:
                continue

            if self.can_complete_beat(beat):
                beat.completed = True
                self.world.discovered_clues.add(beat.clue_unlocked)
                advanced.append(beat.summary)
                self.log(f"Story Progressed: Beat {beat.id} completed - {beat.title}")
                break

        if self.is_solved():
            return self.final_reveal()

        if advanced:
            return "\nStory Progress: " + advanced[0]

        return ""

    def can_complete_beat(self, beat):
        trigger_requirements = {
            3: {"linda motive"},          # Confront Linda should require talking to Linda
            5: {"ledger"},               # Verify bank records should require examining ledger
            7: {"contradicted alibi"},   # Confront Thomas should require talking to Thomas
            9: {"drawer documents"},     # Open drawer should require actually opening/examining it
        }

        if beat.location != self.world.current_location:
            return False

        for item_name in beat.required_items:
            item = self.items.get(item_name)
            if item and item.destroyed:
                return False
            if item_name not in self.world.inventory and item_name not in self.world.discovered_clues:
                return False

        for npc_name in beat.required_npcs:
            npc = self.npcs.get(npc_name)
            if not npc or not npc.alive:
                return False
            if npc.location != self.world.current_location:
                return False

        required_triggers = trigger_requirements.get(beat.id, set())
        if required_triggers and not required_triggers.issubset(self.world.discovered_clues):
            return False

        return True

    def update_dynamic_world(self):
        beat5_done = any(beat.id == 5 and beat.completed for beat in self.story_plan)
        if beat5_done and not self.world.flags["coast_meeting_scheduled"]:
            self.npcs["linda"].location = "coast"
            self.npcs["gregory"].location = "coast"
            self.world.flags["coast_meeting_scheduled"] = True
            self.log("World Event: Linda and Gregory moved to the coast for a secret meeting")

        if "ensure no witnesses memo" in self.world.discovered_clues and not self.world.flags["final_confrontation_ready"]:
            self.npcs["gregory"].location = "museum hall"
            self.npcs["thomas"].location = "museum hall"
            self.world.flags["final_confrontation_ready"] = True
            self.log("World Event: Final confrontation triggered in museum hall")

    # -----------------------------
    # Drama Manager: Exception Detection + Accommodation
    # -----------------------------

    def handle_exception(self, target):
        """
        Template 2 logic:
        If user breaks a required future condition, repair the story plan.
        """

        # Destroying / killing important things
        if target in self.items:
            self.items[target].destroyed = True
            self.log(f"Exceptional Action: player destroyed {target}")
            repair_result = self.repair_story_plan(target, "item_destroyed")
            story_result = self.evaluate_story()
            return repair_result + (f"\n{story_result}" if story_result else "")

        if target in self.npcs:
            self.npcs[target].alive = False
            self.log(f"Exceptional Action: player harmed {target}")
            repair_result = self.repair_story_plan(target, "npc_removed")
            story_result = self.evaluate_story()
            return repair_result + (f"\n{story_result}" if story_result else "")

        # If target is unclear, treat as consistent but not useful
        self.log(f"Consistent Action: attempted disruptive action on unknown target {target}")
        return "You attempt something disruptive, but it does not affect any important evidence or character."

    def repair_story_plan(self, target, reason):
        affected_beats = []

        for beat in self.story_plan:
            if beat.completed:
                continue

            if target in beat.required_items or target in beat.required_npcs:
                beat.invalidated = True
                affected_beats.append(beat)

        if not affected_beats:
            return f"You alter {target}, but the main investigation can still continue."

        replacement_clue = f"alternate evidence replacing {target}"
        replacement_beat = PlotBeat(
            id=max(b.id for b in self.story_plan) + 1,
            title=f"Recover alternate path after losing {target}",
            location=self.world.current_location,
            required_items=[],
            required_npcs=[],
            clue_unlocked=replacement_clue,
            summary=f"Because {target} is no longer usable, you discover an alternate clue that preserves the path to the truth.",
        )

        # Insert replacement before final reveal
        self.story_plan.insert(-1, replacement_beat)
        self.log(f"Accommodation Triggered: invalidated {len(affected_beats)} beat(s)")
        self.log(f"Story Plan Repaired: added replacement beat '{replacement_beat.title}'")

        return (
            f"⚠️ Story Broken: Your action made part of the original mystery path impossible.\n"
            f"Accommodation: The story adapts. Since {target} can no longer be used, "
            f"the investigation now opens an alternate evidence path."
        )

    def is_solved(self):
        return any(beat.id == 13 and beat.completed for beat in self.story_plan)

    def final_reveal(self):
        return (
            "\nFINAL REVEAL:\n"
            "You have enough evidence to accuse Thomas Blake. The poison, financial records, "
            "contradicted alibi, unauthorized funds, and final memo reveal the truth: "
            "Thomas murdered Evelyn Harper to protect his ambitions, with Gregory helping cover the tracks."
        )

    def show_debug(self):
        if not self.debug_log:
            return "Debug log is empty."
        return "\n".join(f"- {entry}" for entry in self.debug_log[-10:])

    def play(self):
        print("\nMYSTERY GAME: The Harper Museum Murder")
        print("Type actions like: go shed, search vial, take ledger, talk linda, destroy key")
        if self.interpreter.llm_enabled:
            print(f"Parser: LLM-enabled ({self.interpreter.model}) with rule fallback.")
        else:
            print("Parser: Rule-based (set OPENAI_API_KEY to enable LLM parsing).")
        print("Type 'debug' to see Drama Manager logs. Type 'quit' to exit.")
        print(self.describe_location())

        while True:
            user_input = input("\n> ").strip()

            if user_input.lower() == "debug":
                print("\nDEBUG / TRACE LOG")
                print(self.show_debug())
                continue

            action = self.interpreter.interpret(user_input)
            result = self.apply_action(action)

            if result == "quit":
                print("Exiting game.")
                break

            print(result)


if __name__ == "__main__":
    game = MysteryGame()
    game.play()