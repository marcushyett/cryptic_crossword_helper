#!/usr/bin/env python3
"""
Generate cryptic crossword hints and full explanations using the OpenAI API.

Inputs:
- game_data.json (from scripts/extract_answers.py)

Outputs:
- hints.json: { "<word_id>": [hint1, hint2, hint3], ... }
- explanations.json: { "<word_id>": { "steps": [..], "device": str, "highlights": [ {"role": str, "text": str} ] } }
- hints_cache.json: persistent cache of API results keyed by (model+prompt_version+clue+answer)

Behavior:
- Up to 10 concurrent API calls
- Single-aspect hints: each of 3 hints labeled (Indicator/Fodder/Definition/Device/Structure/Surface/Grammar/Link/Position)
- Full explanation JSON with steps and highlight tokens
- Validation to ensure proper JSON and no answer leakage
- Skips network if OPENAI_API_KEY is missing; produces empty hints/explanations files
"""
import concurrent.futures
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error


OPENAI_API_URL = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
# The requested model name can be overridden; default to a widely available model
MODEL = os.environ.get("HINTS_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
MAX_WORKERS = int(os.environ.get("HINTS_CONCURRENCY", "10"))
CACHE_FILE = os.environ.get("HINTS_CACHE_FILE", "hints_cache.json")
PROMPT_VERSION = os.environ.get("HINTS_PROMPT_VERSION", "v4-2025-08-31")


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def cache_key(model: str, clue_text: str, answer: str) -> str:
    h = hashlib.sha256()
    key_str = (
        f"model={model}\nprompt_version={PROMPT_VERSION}\nclue={clue_text.strip()}\nanswer={answer.strip()}"
    ).encode("utf-8")
    h.update(key_str)
    return h.hexdigest()


SYSTEM_PROMPT = (
    "You are an expert cryptic crossword setter and teacher. Provide precise, non-spoiler guidance. "
    "Given a clue and its true answer (for validation only), craft exactly three concise hints without revealing the answer. "
    "Each hint should focus on ONE most helpful aspect. Use one of these labels at the start of each hint: "
    "'Indicator:', 'Fodder:', 'Definition:', 'Device:', 'Structure:', 'Surface:', 'Grammar:', 'Link:', 'Position:'. "
    "- Indicator: name the exact word(s) signalling the device (e.g., broken, wild, inside, back, heard). "
    "- Fodder: name the exact letters/word(s) to be manipulated or used (or say 'N/A' if not applicable). "
    "- Definition: name the exact definition word(s). If &lit, say 'Definition: entire clue (&lit)'. "
    "- Device: state the clue type (anagram, container, hidden, reversal, homophone, deletion, insertion, initials/ends, charade, double definition, &lit). "
    "- Structure/Position/Link/Grammar/Surface: highlight helpful structure (e.g., joiners like 'with', link words, enumeration, up/down reversal cues, punctuation tricks). "
    "Always quote or clearly identify the exact clue token(s) for the chosen aspect. Do not repeat the same aspect unless strongly justified by the clue. "
    "Keep each hint under 160 characters. Never output or spell the answer. Output strictly a JSON array of three strings, nothing else."
)


def build_user_prompt(clue_text: str, answer: str, length: str, direction: str = "") -> str:
    dir_line = f"\nDirection: {direction}" if direction else ""
    return (
        "Clue: "
        + clue_text.strip()
        + dir_line
        + "\nAnswer length: "
        + str(length)
        + "\nYou know the answer is '"
        + answer.strip()
        + "' but you must not reveal, spell, or anagram this string in any hint.\n"
    + "Produce three hints. Each hint must start with exactly one label from: Indicator, Fodder, Definition, Device, Structure, Surface, Grammar, Link, Position.\n"
    + "Name the exact clue tokens for the chosen aspect. If fodder not applicable, choose a different aspect. Do not repeat aspects unless helpful.\n"
        + "Return only a JSON array of exactly three strings."
    )


def openai_chat_completion(api_key: str, system_prompt: str, user_prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        # Encourage JSON output; some models support response_format
        "temperature": 0.7,
        "n": 1,
    }
    req = urllib.request.Request(
        OPENAI_API_URL, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            return content
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode("utf-8")
        except Exception:
            err = str(e)
        raise RuntimeError(f"OpenAI API error: {e.code} {err}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"OpenAI API network error: {e}")


def validate_hints(raw_text: str, answer: str) -> list:
    """Parse JSON array, ensure 3 strings and none leak the answer."""
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Sometimes models wrap in code fences or add text; attempt to extract JSON array
        start = raw_text.find("[")
        end = raw_text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(raw_text[start : end + 1])
            except Exception:
                raise ValueError("Failed to parse JSON array from model output")
        else:
            raise ValueError("Model output not JSON array")

    if not isinstance(parsed, list) or len(parsed) != 3:
        raise ValueError("Expected exactly 3 hints in a JSON array")
    out = []
    ans_lower = answer.strip().lower()
    allowed_labels = {"indicator", "fodder", "definition", "device", "structure", "surface", "grammar", "link", "position"}
    for item in parsed:
        if not isinstance(item, str):
            raise ValueError("Hints must be strings")
        # Remove trailing periods and trim
        hint = item.strip()
        # Basic leakage check: do not include the exact answer substring
        if ans_lower and ans_lower in hint.lower():
            raise ValueError("Hint leaks the answer")
        # Require a single leading label from the allowed set
        if ":" not in hint:
            raise ValueError("Each hint must start with a label and colon")
        label = hint.split(":", 1)[0].strip().lower()
        if label not in allowed_labels:
            raise ValueError("Invalid or missing hint label")
        # Passed minimal validation
        out.append(hint)
    return out


def generate_hints_for_clue(api_key: str, clue: dict) -> list:
    # Clue fields expected: word_id, clue, answer, length
    user_prompt = build_user_prompt(
        clue.get("clue", ""), clue.get("answer", ""), clue.get("length", ""), clue.get("direction", "")
    )
    # Try up to 2 attempts
    attempts = 0
    last_err = None
    while attempts < 2:
        attempts += 1
        raw = openai_chat_completion(api_key, SYSTEM_PROMPT, user_prompt)
        try:
            hints = validate_hints(raw, clue.get("answer", ""))
            return hints
        except Exception as e:
            last_err = e
            # tighten prompt on retry
            user_prompt = (
                user_prompt
                + "\nIMPORTANT: Output ONLY a JSON array of exactly three string hints. Do not include any other text."
            )
            time.sleep(0.5)
    raise RuntimeError(f"Failed to generate valid hints after retries: {last_err}")


EXPL_SYSTEM_PROMPT = (
    "You are an expert cryptic crossword setter and teacher. Provide a clear, numbered explanation for one clue. "
    "Include: (1) the device name (anagram/container/hidden/reversal/homophone/deletion/insertion/initials/charade/double definition/&lit), "
    "(2) 3-6 numbered steps that cite the exact clue word(s) for each role, and (3) a highlight map. "
    "In steps, explicitly state: indicator token(s), fodder token(s) (if any), definition token(s), and any substitutions or abbreviations (e.g., 'way' => 'ST'). "
    "Each step must begin with '1.', '2.', etc. Use only clue tokens when naming parts, with brief parenthetical rationale (e.g., "
    "'Indicator: 'broken' (anagram cue)'). "
    "Output strictly a JSON object with keys: 'device' (string), 'steps' (array of strings), and 'highlights' (array of {role:'indicator|fodder|definition', text:'exact tokens from clue'}). "
    "Never reveal or spell the answer."
)


def build_expl_user_prompt(clue_text: str, answer: str, length: str, direction: str = "") -> str:
    dir_line = f"\nDirection: {direction}" if direction else ""
    return (
        "Clue: "
        + clue_text.strip()
        + dir_line
        + "\nAnswer length: "
        + str(length)
        + "\nYou know the answer is '"
        + answer.strip()
        + "' but you must not reveal, spell, or anagram this string in any explanation.\n"
        + "Return only JSON with: device; steps as 3-6 numbered strings citing exact tokens plus roles (indicator/fodder/definition) and any substitutions; highlights array marking tokens by role."
    )


def validate_explanation(raw_text: str, answer: str) -> dict:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        # Attempt to extract object
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(raw_text[start : end + 1])
        else:
            raise ValueError("Explanation not valid JSON object")
    if not isinstance(data, dict):
        raise ValueError("Explanation must be a JSON object")
    device = data.get("device", "").strip()
    steps = data.get("steps", [])
    highlights = data.get("highlights", [])
    if not isinstance(device, str):
        raise ValueError("device must be string")
    if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
        raise ValueError("steps must be array of strings")
    if not (1 <= len(steps) <= 10):
        raise ValueError("steps must contain 1-10 items")
    if not isinstance(highlights, list):
        raise ValueError("highlights must be array")
    for h in highlights:
        if not isinstance(h, dict):
            raise ValueError("highlight item must be object")
        role = str(h.get("role", "")).lower()
        text = str(h.get("text", ""))
        if role not in {"indicator", "fodder", "definition"}:
            raise ValueError("invalid highlight role")
        # leakage check
        if answer.strip().lower() in text.strip().lower():
            raise ValueError("highlight leaks answer")
    # Also check steps don’t leak
    ans_lower = answer.strip().lower()
    for s in steps:
        if ans_lower and ans_lower in s.lower():
            raise ValueError("step leaks answer")
    return {"device": device, "steps": steps, "highlights": highlights}


def main():
    if len(sys.argv) not in (3, 4):
        print("Usage: python scripts/generate_hints.py <game_data.json> <hints.json> [explanations.json]")
        sys.exit(1)

    game_data_path = sys.argv[1]
    hints_out_path = sys.argv[2]
    expl_out_path = sys.argv[3] if len(sys.argv) == 4 else "explanations.json"

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # No API key; try to reconstruct outputs from cache to avoid empty site
        game_data = load_json(game_data_path, {})
        clues = game_data.get("clues", [])
        cache = load_json(CACHE_FILE, {})
        hints_result = {}
        expl_result = {}
        for clue in clues:
            word_id = str(clue.get("word_id"))
            if not word_id:
                continue
            key = cache_key(MODEL, clue.get("clue", ""), clue.get("answer", ""))
            if key in cache:
                entry = cache[key]
                if "hints" in entry:
                    hints_result[word_id] = entry["hints"]
                if "explanation" in entry and entry["explanation"]:
                    expl_result[word_id] = entry["explanation"]

        # Only write files if we have some data, or the targets don't exist yet
        def maybe_write(path, data):
            if data:
                save_json(path, data)
                return True
            # If file doesn't exist, write empty; else leave as-is
            if not os.path.exists(path):
                save_json(path, {})
                return True
            return False

        wrote_hints = maybe_write(hints_out_path, hints_result)
        wrote_expl = maybe_write(expl_out_path, expl_result)
        print(
            "OPENAI_API_KEY not set; materialized from cache: "
            f"hints={len(hints_result)} expl={len(expl_result)}; wrote_hints={wrote_hints} wrote_expl={wrote_expl}"
        )
        return

    game_data = load_json(game_data_path, {})
    clues = game_data.get("clues", [])
    if not clues:
        save_json(hints_out_path, {})
        print("No clues found; generated empty hints.json")
        return

    cache = load_json(CACHE_FILE, {})
    hints_result = {}
    expl_result = {}

    # Prepare work lists
    # - work_full: no cache entry; generate both hints and explanation
    # - work_expl_only: cache has hints but no explanation; generate explanation only
    work_full = []
    work_expl_only = []
    for clue in clues:
        word_id = str(clue.get("word_id"))
        if not word_id:
            continue
        key = cache_key(MODEL, clue.get("clue", ""), clue.get("answer", ""))
        if key in cache:
            # Reuse cached hints
            cached_entry = cache[key]
            hints_result[word_id] = cached_entry.get("hints", [])
            if "explanation" in cached_entry and cached_entry["explanation"]:
                expl_result[word_id] = cached_entry["explanation"]
            else:
                # Need to generate explanation only
                work_expl_only.append((word_id, key, clue))
        else:
            work_full.append((word_id, key, clue))

    def generate_explanation_for_clue(api_key: str, clue_obj: dict) -> dict:
        """Generate an explanation with up to 2 attempts to avoid leakage and formatting issues."""
        expl_prompt = build_expl_user_prompt(
            clue_obj.get("clue", ""), clue_obj.get("answer", ""), clue_obj.get("length", ""), clue_obj.get("direction", "")
        )
        attempts = 0
        last_err = None
        while attempts < 2:
            attempts += 1
            raw_expl = openai_chat_completion(api_key, EXPL_SYSTEM_PROMPT, expl_prompt)
            try:
                return validate_explanation(raw_expl, clue_obj.get("answer", ""))
            except Exception as e:
                last_err = e
                # tighten prompt on retry
                expl_prompt = (
                    expl_prompt
                    + "\nIMPORTANT: Do NOT reveal or spell the answer in any step or highlight. Use only clue tokens; keep steps generic. Return ONLY JSON object."
                )
                time.sleep(0.5)
        raise RuntimeError(f"Failed to generate valid explanation after retries: {last_err}")

    def task(item):
        wid, key, clue_obj = item
        hints = generate_hints_for_clue(api_key, clue_obj)
        explanation = generate_explanation_for_clue(api_key, clue_obj)
        return wid, key, hints, explanation

    def task_expl_only(item):
        wid, key, clue_obj = item
        explanation = generate_explanation_for_clue(api_key, clue_obj)
        return wid, key, explanation

    # Execute work in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = []
        if work_full:
            futures.extend([ex.submit(task, it) for it in work_full])
        if work_expl_only:
            futures.extend([ex.submit(task_expl_only, it) for it in work_expl_only])

        for fut in concurrent.futures.as_completed(futures):
            try:
                result = fut.result()
                # Discriminate by tuple size
                if len(result) == 4:
                    wid, key, hints, explanation = result
                    hints_result[wid] = hints
                    expl_result[wid] = explanation
                    cache[key] = {"hints": hints, "explanation": explanation, "ts": int(time.time())}
                else:
                    wid, key, explanation = result
                    # Keep existing hints_result[wid]
                    expl_result[wid] = explanation
                    cache_entry = cache.get(key, {})
                    cache[key] = {"hints": cache_entry.get("hints", hints_result.get(wid, [])), "explanation": explanation, "ts": int(time.time())}
            except Exception as e:
                # On failure, skip this clue
                sys.stderr.write(f"Generation failed for a clue: {e}\n")

    # Persist outputs
    save_json(hints_out_path, hints_result)
    save_json(expl_out_path, expl_result)
    save_json(CACHE_FILE, cache)
    print(f"Generated hints/explanations for {len(hints_result)} clues; cached: {len(cache)} entries")


if __name__ == "__main__":
    main()
