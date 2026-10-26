"""Password hashing and password rules for shop accounts.

Stored format: pbkdf2_sha256$<iterations>$<salt>$<hex digest>, so the settings
travel with each hash. New hashes use ITERATIONS; older, weaker hashes still
verify and are upgraded the next time that person logs in (see needs_rehash).

Password rules follow NIST SP 800-63B: a minimum length, a maximum so huge inputs
can't tie up the server, and a block on guessable passwords (common passwords,
keyboard patterns, the person's own name or email, and Yale/shop words that an
attacker, human or AI, would try first). No forced symbols or digits.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from zxcvbn import zxcvbn

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000      # OWASP's current recommendation for PBKDF2-HMAC-SHA256
SEED_ITERATIONS = 120_000  # what the original seed accounts used
SALT_BYTES = 16

MIN_LENGTH = 12
MAX_LENGTH = 128
MIN_STRENGTH = 3  # zxcvbn score 0-4; 3 = "safely unguessable" against online and slow offline attacks

# Words an attacker targeting this shop would try first.
SITE_WORDS = [
    "yale", "bulldog", "bulldogs", "handsome dan", "boola", "eli", "elis", "new haven",
    "campus", "customs", "campuscustoms", "campus customs", "shop", "password",
]


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"{ALGORITHM}${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algorithm != ALGORITHM:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    return hmac.compare_digest(candidate, digest)


def needs_rehash(stored: str) -> bool:
    """True if a hash was made with weaker settings than today's."""
    parts = stored.split("$")
    return len(parts) != 4 or parts[0] != ALGORITHM or int(parts[1]) < ITERATIONS or len(parts[2]) < SALT_BYTES * 2


# Verifying against this when an email has no account takes the same time as a real
# check, so response timing can't reveal which emails are registered.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def password_problems(password: str, first_name: str = "", last_name: str = "", email: str = "") -> list[str]:
    """Plain-language reasons a new password isn't allowed; empty if it's fine."""
    if len(password) < MIN_LENGTH:
        return [f"Use at least {MIN_LENGTH} characters."]
    if len(password) > MAX_LENGTH:
        return [f"Use {MAX_LENGTH} characters or fewer."]
    local_part = email.split("@")[0]
    personal = [w for w in (first_name, last_name, email, local_part) if w]
    guessable = personal + SITE_WORDS
    result = zxcvbn(password, user_inputs=guessable)
    if result["score"] >= MIN_STRENGTH:
        # zxcvbn multiplies the guesses for each piece, so stringing together a name, a
        # Yale word and a year can look strong. Someone who knows the person (or an AI
        # that looked them up) tries exactly those, so the rest must be strong on its own.
        known = {m["token"].lower() for m in result["sequence"] if m.get("dictionary_name") == "user_inputs"}
        if not known:
            return []
        rest = password
        for word in sorted(known, key=len, reverse=True):
            rest = re.sub(re.escape(word), "", rest, flags=re.IGNORECASE)
        if len(rest) >= 8 and zxcvbn(rest, user_inputs=guessable)["score"] >= MIN_STRENGTH:
            return []
        return [
            "This password leans on your name, email or Yale words, which are the first things an attacker tries.",
            "Add a few unrelated words of your own, or use a password manager to generate one.",
        ]
    feedback = result["feedback"]
    problems = ["This password is too easy to guess."]
    if feedback.get("warning"):
        problems.append(feedback["warning"].rstrip(".") + ".")
    problems += feedback.get("suggestions", [])
    if not feedback.get("suggestions"):
        problems.append("Try a longer phrase of several unrelated words.")
    return problems
