# Incident: secret-detection drill 

## What happened
A fake GHCR token string was planted in a throwaway file and caught by
a local `gitleaks` scan before it reached any shared branch.

Note: an initial attempt with a low-entropy placeholder (`ghp_XXXX...`,
all repeated characters) was NOT flagged — gitleaks' github-pat rule
combines a regex pattern match with an entropy check, and a
maximally-repetitive string falls below the threshold for a genuine
secret. A second attempt with realistic, high-entropy characters
(entropy 5.12) was flagged correctly. This confirmed the detector
relies on both signals, not pattern-matching alone.

## Response (in order — this order is not negotiable)

1. **ROTATE FIRST.** Treat any leaked token as burned the moment it's
   committed, even locally, even before any push. Revoke it at the
   source and issue a replacement. Rotate related credentials too —
   assume lateral discovery, not just the one credential.
2. **CLEAN HISTORY SECOND, only after rotation.** Remove the file,
   rewrite history if it already reached a shared branch, force-push
   with the team's awareness. Deleting a commit does NOT un-leak a
   live credential — it only cleans up evidence after the credential
   is already safe.
3. Add `gitleaks` as a required CI check so this class of leak cannot
   merge silently again.

The wrong instinct — deleting the commit and considering it resolved —
is not fine: the secret is already in every clone, every fork, and any
backup taken before cleanup. Rotation always comes first.
