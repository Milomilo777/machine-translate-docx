# machine-translate-docx
## Changelog & Updates

### V5.1 Deployment - Subtitle Alignment Engine
- Deployed **V5.1 JSON Router**: Implemented a hardened single-level object prompt with a reserved `_reasoning` meta-key for strict subtitle alignment.
- **Mathematical Duplication (A+B)**: Enforced strict concatenation for merged lines with zero text normalization allowed, alongside guaranteed numeric key sorting.
- **Fallback Safety Net**: Added a Python-level `try-except` fallback catching `json.JSONDecodeError` to guarantee a safe `KEEP_SEPARATE` bypass and prevent pipeline crashes.
- **API Determinism**: Locked `temperature=0` during alignment to ensure reproducible, predictable routing.
