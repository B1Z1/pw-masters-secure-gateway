def _split_system_and_turns(
    messages: list[ChatMessage],
) -> tuple[str | None, list[dict]]:
    """Wydziela i scala treść system; scala sąsiednie komunikaty tej samej roli.

    Zwraca (system, turns); system to None, gdy brak treści systemowej.
    """
    system_parts = [
        message.content for message in messages if message.role == "system"
    ]
    system = _SEPARATOR.join(system_parts) if system_parts else None

    turns: list[dict] = []
    for message in messages:
        if message.role == "system":
            continue
        if turns and turns[-1]["role"] == message.role:
            turns[-1]["content"] += _SEPARATOR + message.content
        else:
            turns.append({"role": message.role, "content": message.content})
    return system, turns
