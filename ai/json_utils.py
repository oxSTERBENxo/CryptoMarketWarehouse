def strip_ai_json_code_fence(text: str) -> str:
    """Some small local models wrap JSON in ``` / ```json fences despite being told not to; strip
    that defensively before parsing rather than failing on an otherwise-valid response. Shared by
    every AI-JSON-response parser (market summary, coin analysis, portfolio review) so they all
    apply the same defensive stripping."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    without_backticks = stripped.strip("`")
    lines = without_backticks.split("\n", 1)
    if len(lines) == 2 and lines[0].strip().lower() in ("", "json"):
        return lines[1].strip()
    return without_backticks.strip()
