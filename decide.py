"""
decide.py - turns the scores into one of four ADRC decisions.

ALLOW      pass through, nothing to do
DELAY      hold it back and warn; the user decides after reading
CHALLENGE  freeze the risky action until the user confirms it is really them
REJECT     drop it and alert the user
"""
from dataclasses import dataclass

ALLOW, DELAY, CHALLENGE, REJECT = "ALLOW", "DELAY", "CHALLENGE", "REJECT"

REJECT_RISK = 80  # blended risk needed to drop a message outright

RULE_TABLE = [
    ("No risky clues (score below the AI threshold)", ALLOW),
    ("AI says low risk", ALLOW),
    ("AI says medium risk, nothing sensitive", DELAY),
    ("AI says medium risk AND asks for money / codes", CHALLENGE),
    ("AI says high risk on something on the screen (page / app)", CHALLENGE),
    ("AI says high risk on a message AND blended risk below 80", CHALLENGE),
    ("AI says high risk on a message AND blended risk 80 or more", REJECT),
]


@dataclass
class Decision:
    action: str
    risk: int
    reason: str
    rule: str


def decide(triage_score: int, sensitive: bool, kind: str, ai) -> Decision:
    """kind is 'message' (can be dropped) or 'screen' (can only be frozen)."""
    if ai is None:
        return Decision(ALLOW, triage_score, "No risky clues were found, so it passed straight through.",
                        RULE_TABLE[0][0])

    risk = round(0.4 * triage_score + 0.6 * ai["risk"])
    reason = ai["reason"]

    if ai["level"] == "low":
        return Decision(ALLOW, risk, reason, RULE_TABLE[1][0])
    if ai["level"] == "medium":
        if sensitive:
            return Decision(CHALLENGE, risk, reason, RULE_TABLE[3][0])
        return Decision(DELAY, risk, reason, RULE_TABLE[2][0])
    # high
    if kind == "screen":
        return Decision(CHALLENGE, risk, reason, RULE_TABLE[4][0])
    if risk >= REJECT_RISK:
        return Decision(REJECT, risk, reason, RULE_TABLE[6][0])
    return Decision(CHALLENGE, risk, reason, RULE_TABLE[5][0])
