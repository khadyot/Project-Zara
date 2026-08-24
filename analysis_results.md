# Deep Audit: Why the Pipeline is Failing (Unlike Project Zen)

You are absolutely right to call this out. The system is currently failing to draft the deep, contextual emails you expect because of three massive structural failures in how the pipeline handles data, rate limits, and fallback scenarios.

Here is the exact breakdown of why your run on `Glen Braganza @ Versapay` completely collapsed compared to the original Project Zen architecture.

## 1. The LLM Brain is Completely Locked Out (Rate Limits)
The most critical issue: **Your LLM API budgets are completely exhausted.**
The ranker and the drafter cannot "read and understand" the signals because they are physically locked out of the AI models.

- **Groq:** You have hit the hard daily limit of 200,000 Tokens Per Day (TPD) for the `on_demand` tier. The system attempted to use Groq, saw `Limit 200000, Used 199405`, and was locked out for 14+ minutes.
- **Gemini:** The system tried to fall back to Gemini, but hit the Free Tier limit of 20 requests per day (`RESOURCE_EXHAUSTED`).
- **Z.ai:** The third fallback also failed due to exhausted quotas.

**Impact:** Because the LLM cannot be reached, the Ranker is throwing exceptions (`scoring unavailable`) for all the valid news articles it actually *did* find (Tavily successfully found 8 articles about Versapay, but the LLM wasn't allowed to read them). The Compound web search is also being skipped entirely.

## 2. Hardcoded Apology Instead of Company Fallback
When the Ranker fails to articulate a specific hook (because of the rate limits), the `drafter.py` is configured to give up. 
Instead of doing what you asked—falling back to a generic company-level research email—the codebase has a hardcoded apology:
> *"I looked across the web... but couldn't find a strong signal..."*

Project Zen likely had a robust fallback that would still attempt to draft a generic pitch based on the company if the person-specific hooks failed. Our current pipeline just throws its hands up and prints a hardcoded string.

## 3. ExaBlog Fetcher is Blindly Passing Bad Data
The `ExaBlog` fetcher crashed with a `400 Invalid URL` error:
`"error":"Invalid URL role - Chief Financial Officer"`

The frontend passed the title "role - Chief Financial Officer" into the pipeline, and the Exa fetcher blindly attempted to use it as a URL string rather than properly parsing the prospect data.

---

## How We Fix This

1. **Fix the API Bottleneck:** We need to either wait for the Groq limits to reset, upgrade the Groq tier, or swap in a fresh API key. Without a working LLM, no "reading and understanding" can happen.
2. **Rip Out the Hardcoded Apology:** I will rewrite `drafter.py`. If no specific person-level hook is found, the drafter must use the LLM to write a generic company-level outreach email based on the company's domain/sector, rather than sending that embarrassing "I couldn't find a signal" template.
3. **Fix Exa Fetcher Validation:** Add validation to the Exa fetchers so they don't crash when handed raw text instead of a domain.
