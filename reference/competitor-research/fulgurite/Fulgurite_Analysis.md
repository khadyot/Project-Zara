# Fulgurite UX & Feature Analysis

This document tracks workflows, features, and UX patterns from **Fulgurite** to identify what we can learn and benchmark against the current state of Project Zebra.

---

## 🧭 Overall Impression
Fulgurite is highly polished and focuses heavily on **frictionless onboarding** and **campaign-level context**. Their biggest strength is that they don't assume the AI knows what the user is selling; they force a "Website Ingestion" step before you can even see a dashboard. The UI is clean, heavily uses stepper-wizards for setup, and provides transparent "Key Reasons" for why a lead was scored poorly, building trust.

---

## 🛠️ Step-by-Step Breakdown

### Step 1: Sender Onboarding & Context Extraction
Instead of hardcoding sender details (like we currently do in `src/lib/config.ts`), Fulgurite dynamically builds the sender's profile.
- **Website Ingestion:** They take the user's URL (`www.zamp.ai`) and use AI to scrape it.
- **ICP Extraction:** Automatically suggests Industry, Target Roles, and Company Size based on the scrape.
- **Positioning Extraction:** Extracts Value Proposition, Customer Pain Points, and Social Proof (quotes/awards).
- **Tone & Goal:** Lets the user pick a tone (Professional, Casual, Bold) and a goal (Book meetings, Drive trials).

![Client Context 0](fulgurite_img0.png)
![Client Context 1](fulgurite_img1.png)
![Screenshot 2](fulgurite_img2.png)
![Screenshot 3](fulgurite_img3.png)
![Screenshot 4](fulgurite_img4.png)
![Screenshot 5](fulgurite_img5.png)
![Screenshot 6](fulgurite_img6.png)
![Screenshot 7](fulgurite_img7.png)

> **Gap Analysis:** We have zero onboarding. We currently hardcode "Alex at Acme Corp". We need a "Sender Profile Setup" flow where users can ingest their website, define their pain points, and store this context in a database to feed into Stage 1 (Identity) and Stage 7 (Drafting).

---

### Step 2: Campaign Creation & Lead Import
Once on the dashboard, the primary unit of work is a **Campaign**.
- **Import:** Supports CSV and Google Sheets links.
- **Mapping:** Visual column mapping UI (First Name, Last Name, Email, LinkedIn, etc.).
- **De-duplication:** Automatically skips duplicates and invalid rows on import.

![Screenshot 8](fulgurite_img8.png)
![Screenshot 9](fulgurite_img9.png)
![Screenshot 10](fulgurite_img10.png)
![Screenshot 11](fulgurite_img11.png)
![Screenshot 12](fulgurite_img12.png)

> **Gap Analysis:** Our pipeline expects an array of prospects but lacks a UI for CSV/GSheets upload and column mapping. We need a Campaign wrapper and an import modal.

---

### Step 3: AI Scoring & Filtration
This is where Fulgurite shines in transparency. After importing, they run a "Scoring" phase.
- **UI Transparency:** Instead of a black box, the UI explicitly shows the "Key Reason" why a lead was rejected or scored low. 
- **Examples:** *"Title 'Future Overlord' is non-standard"* or *"Title 'Developer' is off-ICP; Zamp targets finance/ops"*.

![Screenshot 13](fulgurite_img13.png)
![Screenshot 14](fulgurite_img14.png)
![Screenshot 15](fulgurite_img15.png)

> **Gap Analysis:** Our Stage 4 (Scoring) outputs a 0-100 score and an explanation, but our UI prototype doesn't expose the "Reason for rejection" clearly in a table format. We should adopt this transparent tabular view for rejected/low-score leads.

---

### Step 4: Multi-Step Sequences & Campaign Context
Fulgurite is not just a single-email drafter; it's a full sequencing engine.
- **Visual Builder:** "First email" -> Wait X days -> "Follow-up 1". 
- **Campaign Overrides:** The context extracted in Step 1 can be overridden per campaign (e.g., targeting a specific pain point for a specific campaign).

![Screenshot 16](fulgurite_img16.png)
![Screenshot 17](fulgurite_img17.png)

> **Gap Analysis:** Our pipeline currently stops at Stage 7 (Drafting a single email). We need to architect our system to support multi-step sequences (cadences), where the AI drafts follow-ups based on the lack of reply to the previous email.

---

### Step 5: Delivery & Settings
- **Settings:** Configurable send times, active days, daily limits, and quirky AI settings like "all lowercase" generation.
- **Auto-Send vs Review:** A toggle to "Send emails directly" vs holding them in drafts.

![Screenshot 18](fulgurite_img18.png)

> **Gap Analysis:** We have a strict "Draft Only" mandate for now, but we lack basic campaign settings (Schedule, Limits) which will be required once we integrate email sending APIs (like Resend or Nylas).

---

## 🧠 Playbook Insights (The AI Workflow)

Fulgurite's playbooks reveal an extremely rigorous internal AI workflow. Bad input creates generic AI emails, so they force structure before drafting.

1. **The "3-Signal Framework" (Stage 3 & 7):** Every draft must have a *Recency* signal (event in last 14-30 days), a *Specificity* signal (proves real research), and a *Relevance* signal (bridge to offer). If there's no recency signal, the lead should be held, not emailed.
2. **Falsifiable Pain Hypothesis (Stage 5):** Before writing, they force the AI to generate 3 distinct "pain hypotheses" based on the recent signal (Obvious, Alternative, Contrarian) and pick the strongest one.
3. **Multi-Variant Drafting:** They generate three variants of the email body (Direct, Curiosity, Value-first) and pick the winner.
4. **Anti-AI QA Scorecard (Stage 7):** They use a strict binary scorecard to ban polite filler ("I hope this finds you well"), abstract corporate verbs ("leverage"), and passive voice. They enforce contractions and fragments to sound human.
5. **The Nurture Layer:** A strict 3-touch follow-up sequence: (1) Clarify original signal, (2) Add one useful observation, (3) Clean permission-based breakup.

---

## 📊 Benchmark Summary: What Zebra needs to build

Based on `Current_State_Process_1255PM_Aug22.md` and the Playbooks, here are the immediate architectural gaps we must cover:

1. **The "Sender Profile" Onboarding Flow:** We need to build a UI (and backend schema) to scrape a user's website and save their Value Prop, ICP, and Social Proof. This replaces our hardcoded `SENDER_OFFERING`.
2. **Campaign Abstraction:** Leads must belong to a Campaign. Campaigns must have their own context overrides.
3. **CSV/Google Sheets Importer:** A standard column-mapping UI to feed leads into our pipeline.
4. **Transparent Scoring UI:** Expose the "Key Reason" from our Stage 4 evaluator directly in the leads table so users trust the AI's filtration.
5. **Upgrade Stage 3 (Research):** Explicitly hunt for a *Recency* signal.
6. **Upgrade Stage 5 & 7 (Strategy & Drafting):** Implement the Falsifiable Pain Hypothesis, Multi-Variant Drafting, and the strict Anti-AI Scorecard into our `stage7-draft.ts` logic.
7. **Sequencing (Future):** We must expand our drafting stage to handle Follow-Up 1, Follow-Up 2, etc., following the 3-touch nurture layer, rather than just a single cold email.
