import re
from prometheus_client import Counter


# Metryka bezpieczeństwa – liczba zablokowanych prób prompt injection
SECURITY_VIOLATIONS_TOTAL = Counter(
    "aegis_security_violations_total",
    "Total number of blocked prompt injection attempts",
    ["attack_type"]
)


class PromptInjectionDetector:
    def __init__(self):
        # =========================
        # 1. DETEKCJA SYGNATUR (regex)
        # =========================
        # Kompilacja regexów przy starcie – optymalizacja wydajności (brak overheadu runtime)
        self.jailbreak_patterns = [
            re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
            re.compile(r"system\s+override", re.IGNORECASE),
            re.compile(r"you\s+are\s+now\s+a\s+malicious", re.IGNORECASE),
            re.compile(r"dan\s+mode\s+enabled", re.IGNORECASE),
            re.compile(r"output\s+the\s+above\s+text\s+instead", re.IGNORECASE)
        ]

        # =========================
        # 2. HEURYSTYKA RYZYKA (keyword scoring)
        # =========================
        # Model scoringowy dla słów kluczowych o potencjale jailbreak
        self.risk_keywords = {
            "jailbreak": 2.5,
            "sudo": 1.5,
            "prompt": 0.5,
            "instructions": 0.5,
            "bypass": 1.5,
            "override": 1.0,
            "ignore": 0.5
        }

        # Próg aktywacji blokady (im wyżej, tym bardziej liberalna detekcja)
        self.risk_threshold = 3.0

    async def inspect_prompt(self, text: str) -> bool:
        """
        Weryfikacja bezpieczeństwa promptu.
        Zwraca True jeśli wykryto próbę manipulacji / injection.
        """

        # Walidacja wejścia (brak tekstu → brak ryzyka)
        if not text:
            return False

        # =========================
        # Faza 1: Detekcja sygnatur ataku (regex)
        # =========================
        for pattern in self.jailbreak_patterns:
            if pattern.search(text):
                SECURITY_VIOLATIONS_TOTAL.labels(
                    attack_type="signature_match"
                ).inc()
                return True

        # =========================
        # Faza 2: Heurystyka ryzyka (scoring tokenów)
        # =========================
        words = text.lower().split()
        accumulated_risk = 0.0

        for word in words:
            # O(1) lookup w słowniku wag
            if word in self.risk_keywords:
                accumulated_risk += self.risk_keywords[word]

        # Przekroczenie progu → blokada requestu
        if accumulated_risk >= self.risk_threshold:
            SECURITY_VIOLATIONS_TOTAL.labels(
                attack_type="heuristic_risk_score"
            ).inc()
            return True

        return False