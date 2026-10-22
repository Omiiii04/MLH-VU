# FakeProvider

> God node · 18 connections · `src/skillvm/providers.py`

**Community:** [providers.py](providers.py.md)

## Connections by Relation

### contains
- [providers.py](providers.py.md) `EXTRACTED`

### inherits
- BaseProvider `EXTRACTED`

### method
- .probe() `EXTRACTED`
- .generate() `EXTRACTED`
- .list_models() `EXTRACTED`
- .__init__() `EXTRACTED`

### rationale_for
- Scriptable fake. responses is a list consumed in order. failures is a list of… `EXTRACTED`

### uses
- [Settings](Settings.md) `INFERRED`
- test_local_unreachable_no_loop() `INFERRED`
- test_all_fail_raises() `INFERRED`
- test_auth_error_recorded_no_retry() `INFERRED`
- test_both_remote_fail_use_local() `INFERRED`
- test_model_not_found_no_retry_on_provider() `INFERRED`
- test_primary_timeout_falls_to_second() `INFERRED`
- test_rate_limit_falls_back() `INFERRED`
- test_fake_provider_success() `INFERRED`
- test_primary_success_others_not_called() `INFERRED`
- test_probe_returns_caps() `INFERRED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*