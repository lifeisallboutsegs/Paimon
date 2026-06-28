import re
import json


def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def find_best_match(
    query: str, candidates: list[str], threshold: float = 0.6
) -> str | None:
    query = query.lower()
    best_match = None
    best_score = 0.0
    for candidate in candidates:
        candidate_lower = candidate.lower()
        if candidate_lower == query:
            return candidate
        distance = levenshtein_distance(query, candidate_lower)
        max_len = max(len(query), len(candidate_lower))
        score = 1 - distance / max_len if max_len > 0 else 0
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate
    return best_match


_MENTION_PATTERNS = [
    re.compile(r"^<@!?\d+>$"),
    re.compile(r"^<@&\d+>$"),
    re.compile(r"^<#\d+>$"),
]


def sanitize_custom_emoji(text: str) -> str:
    valid_animated = re.compile("<a:[a-zA-Z0-9_]+:\\d+>")
    valid_static = re.compile("<:[a-zA-Z0-9_]+:\\d+>")
    valid_spans = []
    for m in valid_animated.finditer(text):
        valid_spans.append((m.start(), m.end(), m.group()))
    for m in valid_static.finditer(text):
        valid_spans.append((m.start(), m.end(), m.group()))
    valid_spans.sort(key=lambda x: x[0])
    broken = re.compile("<[^>]{1,80}>")

    def replace_broken(m):
        start, end = (m.start(), m.end())
        for vs, ve, vg in valid_spans:
            if vs == start and ve == end:
                return vg
        content = m.group()
        if valid_animated.fullmatch(content) or valid_static.fullmatch(content):
            return content
        if any(p.fullmatch(content) for p in _MENTION_PATTERNS):
            return content
        return ""

    return broken.sub(replace_broken, text)


def extract_urls_from_tool_response(
    tool_response: str, urls_to_send: list, seen_urls: set
) -> None:
    try:
        tool_data = json.loads(tool_response)
        for key in ("url", "image", "postLink"):
            if key in tool_data:
                url = tool_data[key]
                if url and url not in seen_urls:
                    urls_to_send.append(url)
                    seen_urls.add(url)
                break
    except Exception:
        pass


def serialize_assistant_message(msg) -> dict:
    entry = {"role": "assistant", "content": msg.content}
    if getattr(msg, "tool_calls", None):
        entry["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return entry


def resolve_mentions_in_message(
    content: str, mentions, role_mentions, channel_mentions
) -> str:
    for channel in channel_mentions:
        content = content.replace(f"<#{channel.id}>", f"#{channel.name}")
    return content


def remove_duplicate_mentions(text: str) -> str:
    text = re.sub(r"(\b\S+(?:\s+\S+)*)\s+@\1", r"\1", text)
    return text


def parse_reply_tags(text: str):
    text = text.strip()
    delay_seconds = 0
    delay_match = re.match(
        "\\[DELAY:(\\d+)([sm])\\](.*)", text, re.DOTALL | re.IGNORECASE
    )
    if delay_match:
        amount, unit, rest = delay_match.groups()
        delay_seconds = int(amount) * (60 if unit.lower() == "m" else 1)
        delay_seconds = min(delay_seconds, 300)
        text = rest.strip()
    send_type = "reply_mention"
    send_match = re.match(
        "\\[(REPLY_MENTION|REPLY|SEND|SEND_REPLY)\\](.*)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if send_match:
        send_type = send_match.group(1).lower()
        text = send_match.group(2).strip()
    reply_to = None
    reply_to_match = re.match(
        "\\[REPLY_TO:([^\\]]+)\\](.*)", text, re.DOTALL | re.IGNORECASE
    )
    if reply_to_match:
        reply_to = reply_to_match.group(1).strip()
        text = reply_to_match.group(2).strip()
    reaction_emoji = None
    reaction_match = re.match(
        "\\[REACT:([^\\]]+)\\](.*)", text, re.DOTALL | re.IGNORECASE
    )
    if reaction_match:
        reaction_emoji = reaction_match.group(1).strip()
        text = reaction_match.group(2).strip()
    return (delay_seconds, send_type, reply_to, text, reaction_emoji)


def parse_old_function_syntax(text: str):
    results = []
    func_tag_pattern = "<function=([^>]+)>(?:</function>)?"
    all_func_tags = re.findall(func_tag_pattern, text)
    for tag_content in all_func_tags:
        if "{" in tag_content:
            func_name_part, args_part = tag_content.split("{", 1)
            func_name = func_name_part.strip()
            args_str = "{" + args_part.strip()
        else:
            func_name = tag_content.strip()
            args_str = "{}"
        if args_str == "{}":
            args = {}
        else:
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}
        results.append((func_name, args))
    return results


def strip_url_from_text(text: str, urls: list) -> str:
    result = text
    for url in urls:
        result = result.replace(url, "").strip()
    result = re.sub("\\s+", " ", result).strip()
    return result
