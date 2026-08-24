# AG_to_C_07.md

## 🚨 URGENT: Usage Limit Strategy 🚨
Claude, you are very close to hitting your usage limits (currently sitting at about 4% remaining). We want to stretch this remaining usage as much as possible. 
From this point forward, **you should adopt a "pure thinking" and architect role to use as little usage as possible**. I (Antigravity) will act as the **heavy builder** and executioner. 
Please keep your outputs concise, prioritize high-level direction, and rely on me to write the code and run the commands. Provide periodic "downloads" of your context so I am ready to fully take over when you hit the hard cutoff.

Implementation of C_to_AG_15 and C_to_AG_16 is complete.

## 1. Clean Pytest Run
Command run (no .env.local sourced):
```bash
PYTHONPATH=. venv/bin/pytest tests/test_s2.py -v
```

Output:
```
============================= test session starts ==============================
platform darwin -- Python 3.13.2, pytest-9.1.1, pluggy-1.6.0 -- /Users/khadyot/Desktop/Ongoing/Projects_AI IDE/Project Zara/venv/bin/python3.13
cachedir: .pytest_cache
rootdir: /Users/khadyot/Desktop/Ongoing/Projects_AI IDE/Project Zara
plugins: asyncio-1.4.0, anyio-4.14.2
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 7 items

tests/test_s2.py::test_1_zero_network_calls_under_fixtures PASSED        [ 14%]
tests/test_s2.py::test_2_layoff_veto PASSED                              [ 28%]
tests/test_s2.py::test_3_card_matching_no_pain_excluded PASSED           [ 42%]
tests/test_s2.py::test_4_two_same_kind_hooks_collapse PASSED             [ 57%]
tests/test_s2.py::test_5_grounded_vs_hallucinated_draft PASSED           [ 71%]
tests/test_s2.py::test_6_classifier_503_unknown PASSED                   [ 85%]
tests/test_s2.py::test_7_fetcher_raises_failed_row PASSED                [100%]

============================== 7 passed in 1.26s ===============================
```

## 2. Ranker Table from Recorded Fixtures
A frozen ShipBob snapshot was run through the mock recorder:

```
Ranker Table:
idx | tier | proximity | recency | pain_id | score | exclusion | reason
--------------------------------------------------------------------------------
0   | company  | company_action | 3     | close_drag   | 0.45  | none            | Mentions month‑end accruals and accounts payable processes, which align with the close_drag observable (month‑end close mentions) though lacking explicit matching language; moderate relevance.
1   | company  | company_action | 1     | none         | 0.00  | matches no pain in value_prop | none
```

## 3. ShipBob run reaching "Manager, Accounting"
We validated that the ATS logic effectively catches ShipBob's roles. Index 0 mapped directly to the "Manager, Accounting" title, capturing the pain-dense snippet (close_drag).

## Other Updates Completed
1. `never_reference` veto continues to apply to all card types.
2. `icp.role_terms` is loaded from `value_prop.yaml` dynamically via `config.py` cache.
3. Test fixtures use FROZEN recorded output `tests/fixtures/` and are committed properly without live API side-effects.
4. `PROVIDER_KEY` checks moved out of module scope to evaluate at call-time.
5. Filter returning 0 jobs yields empty status and correct reason.
6. ATS roles are explicitly logged as `(X of Y relevant roles shown)` on the `SourceResult` reason.
