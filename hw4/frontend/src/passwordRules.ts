// Same limits the server enforces (passwords.py); the server also refuses guessable passwords.
export const MIN_PASSWORD_LENGTH = 12
export const MAX_PASSWORD_LENGTH = 128
export const PASSWORD_HINT =
  `At least ${MIN_PASSWORD_LENGTH} characters. A phrase of several unrelated words works well. ` +
  "Avoid your name, email or Yale words; they're the first things attackers try."
