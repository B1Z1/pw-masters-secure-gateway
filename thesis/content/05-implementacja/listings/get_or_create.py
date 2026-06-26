class MappingStore:
    ...

    async def get_or_create(self, session_id: str, entity: DetectedEntity) -> str:
        # Szeregowanie per sesja: równoległe żądania o ten SAM oryginał nie mogą
        # wygenerować różnych zamienników (wyścig odczyt-zapis złamałby zasadę
        # „ten sam oryginał -> ten sam zamiennik"). Blokada działa w obrębie procesu.
        async with self._session_locks.lock(session_id):
            return await self._substitute(session_id, entity)
