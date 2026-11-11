# StaleCheck — 3-Minute Demo Script & Pitch Guide

## The Problem (0:00 – 0:30)
"Large Language Models speak with uniform confidence regardless of whether their training data is 3 days or 3 years old. In fast-moving domains—API versions, SaaS pricing, executive leadership, legal regulations—this silent decay causes costly errors. 

StaleCheck solves this by intercepting AI-generated text, isolating time-sensitive factual claims, and verifying them against live web evidence retrieved via Tavily. Independent multi-model evaluation through Maxim AI's Bifrost gateway calculates a 0–100 freshness score and surgically rewrites outdated claims with verified markdown citations."

---

## 3-Minute Live Demonstration Flow

### Scene 1: Initial Answer Verification (0:30 – 1:15)
1. **Action**: Open the StaleCheck dashboard (`http://localhost:8000`).
2. **Action**: Switch to the "Verify Existing Answer" tab.
3. **Input Example**:
   > *"OpenAI GPT-4 charges $0.03 per 1,000 prompt tokens. The CEO of Twitter is Parag Agrawal. Python 3.12 was released in October 2023."*
4. **Action**: Click **"Analyze Freshness"**.
5. **What to highlight**:
   - The **5-Stage Stepper** lights up in real-time via Server-Sent Events (SSE):
     - Extract -> Search -> Analyze -> Judge -> Rewrite.
   - Note the sub-second latency and parallel search query execution.

### Scene 2: Freshness Score & Claim Breakdown (1:15 – 2:00)
1. **What to show**:
   - The **Conic Freshness Gauge** displays an aggregate freshness score (e.g., 28/100, Stale).
   - The **Claim Cards**:
     - *Claim 1*: Pricing ($0.03/1k tokens) -> **Stale** (Score: 15).
       - Expand evidence accordion: Shows live OpenAI pricing page snippet retrieved via Tavily.
     - *Claim 2*: Leadership (Twitter CEO Parag Agrawal) -> **Stale** (Score: 10).
       - Shows current executive leadership changes.
     - *Claim 3*: Version / Release date (Python 3.12) -> **Fresh** (Score: 92) or identified as a stable fact.
   - The **Stable Facts Accordion**: Separates timeless facts (e.g. historical release events) from ongoing dynamic state.

### Scene 3: Surgical Diff & Evidence Citations (2:00 – 2:40)
1. **What to show**:
   - Scroll to the **Answer Comparison & Diff** view.
   - Word-level red `<del>` and green `<ins>` highlights:
     - Only the stale facts are altered; formatting and non-stale sentences are untouched.
     - Notice the verified markdown source links `[source](https://...)` directly attached to corrections.
   - The **Deduplicated Sources List**: Displays all unique domains and publication dates that backed the judgments.

### Scene 4: Export & Mock Mode Capabilities (2:40 – 3:00)
1. **Action**: Click **"Export Markdown"** or **"Copy Diff"**.
2. **Action**: Demonstrate zero-cost offline demonstration using `?mock=1` or the built-in Mock Mode toggle in the top bar.
3. **Closing Remark**:
   > *"StaleCheck brings real-time factual integrity to AI answers—combining Tavily's fresh web retrieval with Bifrost's independent multi-model judging for trustworthy, production-grade AI outputs."*
