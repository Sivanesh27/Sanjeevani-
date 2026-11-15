"""
Personalised drug-interaction engine.

Pipeline for one patient:
  1. Normalise meds against the knowledge base (brand/misspelling aware); unknown meds are reported, never silently ignored.
  2. Pairwise interactions: curated rule (source of truth) -> ML estimate only when no rule exists (shown separately, lower weight).
  3. Personalised risk score 0-100 per interaction = base severity + transparent, explainable patient factors
     (age, kidney/liver function, pregnancy, conditions, labs, lifestyle, polypharmacy).
  4. Drug-condition precautions, drug-allergy alerts, monitoring plan, personalised diet plan, questions for the doctor.
This is a rules-driven clinical decision-support aid, NOT a model trained on patient outcomes.
"""
import itertools
from datetime import date
from ..data.lexicons import CONDITIONS, ALLERGENS
from .kb import KB, norm

BASE = {"Minor": 18, "Moderate": 42, "Major": 62}
LEVELS = [(75, "Critical"), (55, "High"), (30, "Moderate"), (0, "Low")]
LEVEL_SCORE = {"Critical": 85, "High": 65, "Moderate": 40, "Low": 15}
DISCLAIMER = ("Sanjeevani AI is a decision-support aid, not a substitute for professional medical advice. "
              "Never start, stop or change a medicine without talking to your doctor or pharmacist. "
              "'No interaction found' means none is recorded in our database - it does not prove a combination is safe.")


def level_for(score: int) -> str:
    return next(l for t, l in LEVELS if score >= t)


def age_from(dob):
    if not dob: return None
    t = date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


def ckd_epi_2021(scr, age, sex):
    if not scr or not age: return None
    female = (sex or "").lower() == "female"
    k, a = (0.7, -0.241) if female else (0.9, -0.302)
    e = 142 * min(scr / k, 1) ** a * max(scr / k, 1) ** -1.2 * 0.9938 ** age * (1.012 if female else 1)
    return round(e, 1)


class Ctx:
    """Patient context with derived flags."""
    def __init__(self, profile: dict, conditions: list[dict]):
        p = profile or {}
        self.p = p
        self.age = p.get("age")
        self.sex = p.get("sex")
        h, w = p.get("height_cm"), p.get("weight_kg")
        self.bmi = round(w / ((h / 100) ** 2), 1) if h and w and h > 50 else None
        self.egfr = p.get("egfr") or ckd_epi_2021(p.get("serum_creatinine"), self.age, self.sex)
        self.egfr_estimated = not p.get("egfr") and self.egfr is not None
        self.keys, self.derived = set(), []
        for c in conditions:
            if c.get("condition_key") and c.get("status", "active") == "active":
                self.keys.add(c["condition_key"])
        def derive(key, why):
            if key not in self.keys:
                self.keys.add(key); self.derived.append({"key": key, "label": CONDITIONS[key]["label"], "why": why})
        if self.age and self.age >= 65: derive("elderly", f"age {self.age}")
        if self.egfr is not None and self.egfr < 60: derive("renal_impairment", f"eGFR {self.egfr}")
        if self.bmi and self.bmi >= 30: derive("obesity", f"BMI {self.bmi}")
        if p.get("pregnant"): derive("pregnancy", "profile")
        if (p.get("alt") or 0) >= 120 or (p.get("ast") or 0) >= 120: derive("hepatic_impairment", "ALT/AST >= 3x normal")
        self.alcohol = p.get("alcohol"); self.smoker = p.get("smoker")

    def has(self, *keys): return any(k in self.keys for k in keys)


# ------------------------------------------------------------------ personalisation factors
# (condition key(s), tag set, points, label, explanation)
FACTORS = [
    (("heart_disease", "heart_failure"), {"qt_risk", "arrhythmia_risk", "bradycardia_risk"}, 10, "Heart disease", "Existing heart disease makes rhythm and heart-rate effects more dangerous."),
    (("diabetes",), {"hypoglycemia_risk", "hyperglycemia_risk"}, 8, "Diabetes", "Blood-sugar swings are harder to control with this combination."),
    (("asthma_copd",), {"arrhythmia_risk", "bradycardia_risk", "cns_depressant", "respiratory_depression_risk"}, 8, "Asthma / COPD", "Breathing problems increase sensitivity to sedatives and rate-slowing drugs."),
    (("seizure_disorder",), {"cns_depressant", "narrow_therapeutic_index"}, 6, "Seizure disorder", "Interacting drugs can destabilise seizure control."),
    (("osteoporosis",), {"absorption_sensitive", "chelation_risk"}, 5, "Osteoporosis", "Bone medicines are easily blocked by co-administered drugs and foods."),
    (("immunocompromised",), {"bone_marrow_suppression_risk", "immunosuppressant"}, 8, "Weakened immunity", "Blood-count and infection risks are amplified."),
    (("peptic_ulcer_history",), {"gi_risk", "bleeding_risk"}, 12, "Past ulcer / GI bleed", "A previous ulcer or bleed makes a new bleed much more likely."),
    (("thyroid_disorder",), {"absorption_sensitive", "hepatic_metabolism"}, 6, "Thyroid disorder", "Thyroid dosing is sensitive to absorption and metabolism changes."),
    (("obesity",), {"hepatic_metabolism", "cyp3a4_substrate"}, 3, "Obesity", "Body size can change how long a drug stays in the body."),
    (("anemia",), {"bone_marrow_suppression_risk", "bleeding_risk"}, 8, "Anemia", "Low blood count leaves less reserve for bleeding or marrow effects."),
    (("glaucoma",), {"anticholinergic_risk"}, 8, "Glaucoma", "Anticholinergic effects can raise eye pressure."),
    (("sleep_apnea",), {"cns_depressant", "respiratory_depression_risk"}, 10, "Sleep apnea", "Sedatives can worsen breathing pauses during sleep."),
    (("hypertension",), {"hypertensive_crisis_risk"}, 5, "High blood pressure", "Blood-pressure spikes are more dangerous."),
    (("pregnancy",), None, 8, "Pregnancy", "Any interaction needs specialist review during pregnancy."),
    (("hepatic_impairment",), {"hepatic_metabolism", "cyp3a4_substrate", "cyp2c9_substrate", "cyp2d6_substrate", "hepatotoxicity_risk"}, 10, "Liver impairment", "A weaker liver clears these drugs more slowly."),
]
ELDER_TAGS = {"cns_depressant", "bleeding_risk", "bradycardia_risk", "hypotension_risk", "narrow_therapeutic_index", "anticholinergic_risk"}
RENAL_TAGS = {"renal_clearance", "nephrotoxicity_risk", "renal_risk", "lactic_acidosis_risk", "hyperkalemia_risk"}
ALCOHOL_TAGS = {"cns_depressant", "bleeding_risk", "hepatic_metabolism", "hepatotoxicity_risk", "lactic_acidosis_risk"}


def personalise(base_pts: int, tags: set, ctx: Ctx, n_meds: int):
    pts, factors = base_pts, []
    def add(label, p, detail):
        nonlocal pts; pts += p; factors.append({"label": label, "points": p, "detail": detail})
    for keys, tagset, p, label, detail in FACTORS:
        if ctx.has(*keys) and (tagset is None or tags & tagset):
            add(label, p, detail)
    if ctx.age and ctx.age >= 65 and tags & ELDER_TAGS:
        add(f"Age {ctx.age}", 8 if ctx.age >= 80 else 5, "Older adults are more sensitive to sedation, bleeding, falls and low blood pressure from these drugs.")
    if ctx.egfr is not None and ctx.egfr < 60:
        sev = ctx.egfr < 30
        if tags & RENAL_TAGS:
            add(f"Kidney function (eGFR {ctx.egfr}{' est.' if ctx.egfr_estimated else ''})", 15 if sev else 8, "Reduced kidney clearance lets these drugs build up.")
    k = ctx.p.get("potassium")
    if k and k > 5.0 and "hyperkalemia_risk" in tags: add(f"High potassium ({k})", 18 if k > 5.5 else 12, "Potassium is already high and this combination can raise it further.")
    if k and k < 3.5 and tags & {"hypokalemia_risk", "qt_risk"}: add(f"Low potassium ({k})", 10, "Low potassium makes dangerous heart rhythms more likely.")
    inr = ctx.p.get("inr")
    if inr and inr > 3.0 and "anticoagulant" in tags: add(f"INR already high ({inr})", 18 if inr > 4 else 12, "Blood is already thinner than the usual target range.")
    a1c = ctx.p.get("hba1c")
    if a1c and a1c >= 8 and tags & {"hypoglycemia_risk", "hyperglycemia_risk"}: add(f"HbA1c {a1c}%", 4, "Poor sugar control leaves less margin for error.")
    hr = ctx.p.get("heart_rate")
    if hr and hr < 50 and "bradycardia_risk" in tags: add(f"Slow pulse ({hr}/min)", 8, "Heart rate is already low.")
    sbp = ctx.p.get("systolic_bp")
    if sbp and sbp < 100 and "hypotension_risk" in tags: add(f"Low blood pressure ({sbp})", 8, "Blood pressure is already low.")
    if ctx.alcohol in ("heavy", "moderate") and tags & ALCOHOL_TAGS:
        add(f"Alcohol use ({ctx.alcohol})", 8 if ctx.alcohol == "heavy" else 3, "Alcohol adds to sedation, bleeding and liver strain.")
    if ctx.smoker == "current" and tags & {"cyp1a2_substrate", "cyp1a2_inhibitor"}:
        add("Smoking", 4, "Smoking speeds up the breakdown of some drugs, so doses behave differently.")
    if n_meds >= 10: add(f"{n_meds} medicines", 8, "Many medicines at once multiply interaction risk.")
    elif n_meds >= 5: add(f"{n_meds} medicines", 4, "Taking five or more medicines raises overall interaction risk.")
    return min(100, pts), factors


# ------------------------------------------------------------------ drug - condition precautions
def _m(classes=(), names=(), tags=()):
    return {"classes": set(classes), "names": set(names), "tags": set(tags)}


PRECAUTIONS = [  # (match, condition key | callable(ctx), level, message, advice)
    (_m(["NSAID"]), "renal_impairment", "High", "NSAIDs reduce blood flow to the kidneys and can worsen kidney function.", "Avoid regular NSAID use; ask about acetaminophen (paracetamol) instead."),
    (_m(["NSAID"]), "peptic_ulcer_history", "Critical", "NSAIDs can reopen an ulcer or cause a GI bleed.", "Avoid NSAIDs; if essential, only with a stomach-protecting medicine and doctor supervision."),
    (_m(["NSAID"]), "heart_failure", "High", "NSAIDs cause fluid retention and can worsen heart failure.", "Avoid NSAIDs and discuss pain relief options."),
    (_m(["NSAID"]), "hypertension", "Moderate", "NSAIDs can raise blood pressure and blunt blood-pressure medicines.", "Use the lowest dose for the shortest time; monitor blood pressure."),
    (_m(["NSAID"]), "pregnancy", "High", "NSAIDs are generally avoided in pregnancy, particularly after 20 weeks.", "Ask your obstetrician before using any NSAID."),
    (_m(names=["Metformin"]), lambda c: c.egfr is not None and c.egfr < 30, "Critical", "Metformin is contraindicated when kidney function (eGFR) is below 30.", "Do not continue without urgent doctor review."),
    (_m(names=["Metformin"]), lambda c: c.egfr is not None and 30 <= c.egfr < 45, "Moderate", "With eGFR 30-44 the metformin dose usually needs reducing.", "Ask your doctor to review the dose."),
    (_m(names=["Propranolol", "Carvedilol", "Timolol"]), "asthma_copd", "High", "Non-selective beta blockers can trigger bronchospasm.", "Ask about a cardio-selective alternative."),
    (_m(["Beta blocker"]), "asthma_copd", "Moderate", "Beta blockers may worsen asthma/COPD at higher doses.", "Prefer cardio-selective agents; report wheeze."),
    (_m(["Benzodiazepine", "Opioid", "Z-drug hypnotic", "Muscle relaxant"]), "sleep_apnea", "High", "Sedatives and opioids can worsen breathing pauses in sleep apnea.", "Avoid or use the lowest dose with monitoring."),
    (_m(["Benzodiazepine", "Z-drug hypnotic", "Opioid", "Muscle relaxant"]), "elderly", "High", "Sedatives raise the risk of falls, confusion and fractures in older adults.", "Ask whether a safer alternative or a lower dose is possible."),
    (_m(["Anticholinergic (overactive bladder)", "First-gen antihistamine", "Tricyclic antidepressant"]), "glaucoma", "High", "Anticholinergic drugs can raise eye pressure and trigger glaucoma attacks.", "Check with your eye specialist before using."),
    (_m(["Anticholinergic (overactive bladder)", "First-gen antihistamine", "Tricyclic antidepressant"]), "elderly", "Moderate", "Strongly anticholinergic drugs can cause confusion, constipation and urine retention in older adults.", "Ask about alternatives."),
    (_m(["ACE inhibitor", "ARB", "Direct renin inhibitor"]), "pregnancy", "Critical", "ACE inhibitors/ARBs can harm an unborn baby.", "Contact your doctor immediately; these are normally stopped in pregnancy."),
    (_m(["Warfarin/VKA anticoagulant"]), "pregnancy", "Critical", "Warfarin can cause birth defects and bleeding.", "Contact your doctor immediately for a safer anticoagulant."),
    (_m(["Statin"]), "pregnancy", "High", "Statins are generally stopped during pregnancy.", "Discuss with your doctor."),
    (_m(["Tetracycline", "Fluoroquinolone"]), "pregnancy", "High", "This antibiotic class is generally avoided in pregnancy.", "Ask your doctor for a pregnancy-safe antibiotic."),
    (_m(names=["Methotrexate"]), "pregnancy", "Critical", "Methotrexate causes miscarriage and birth defects.", "Urgent specialist advice is needed."),
    (_m(names=["Methotrexate"]), "renal_impairment", "Critical", "Methotrexate is cleared by the kidneys and can reach toxic levels.", "Needs specialist dose adjustment and close monitoring."),
    (_m(names=["Methotrexate"]), "hepatic_impairment", "High", "Methotrexate can injure the liver.", "Needs specialist review and liver monitoring."),
    (_m(["Statin"]), "hepatic_impairment", "High", "Statins can raise liver enzymes; caution in active liver disease.", "Discuss liver tests with your doctor."),
    (_m(["Non-dihydropyridine CCB"]), "heart_failure", "High", "Verapamil/diltiazem can worsen heart failure with reduced pumping function.", "Ask your cardiologist whether this is appropriate."),
    (_m(tags=["qt_risk"]), "heart_disease", "High", "This medicine can prolong the QT interval and trigger dangerous heart rhythms.", "Ask about an ECG and an alternative if possible."),
    (_m(["Tricyclic antidepressant"]), "heart_disease", "High", "Tricyclics can cause arrhythmias in people with heart disease.", "Ask about safer antidepressants."),
    (_m(["Nasal decongestant"]), "hypertension", "High", "Decongestants raise blood pressure.", "Avoid; try saline spray or ask your pharmacist."),
    (_m(["Nasal decongestant"]), "heart_disease", "High", "Decongestants can trigger palpitations and raise blood pressure.", "Avoid unless your cardiologist agrees."),
    (_m(["Corticosteroid"]), "diabetes", "Moderate", "Steroids raise blood sugar.", "Monitor glucose closely during treatment."),
    (_m(["Antipsychotic (atypical, metabolic risk)"]), "diabetes", "Moderate", "Olanzapine/clozapine can worsen blood sugar and weight.", "Regular glucose and weight monitoring."),
    (_m(["Corticosteroid"]), "osteoporosis", "Moderate", "Long-term steroids weaken bones.", "Discuss bone protection (calcium, vitamin D)."),
    (_m(["Corticosteroid"]), "peptic_ulcer_history", "Moderate", "Steroids add to stomach-ulcer risk.", "Ask about stomach protection."),
    (_m(["Fluoroquinolone"]), "seizure_disorder", "High", "Fluoroquinolones can lower the seizure threshold.", "Ask for a different antibiotic."),
    (_m(names=["Tramadol"]), "seizure_disorder", "High", "Tramadol can lower the seizure threshold.", "Ask for a different pain medicine."),
    (_m(["Antiplatelet", "Warfarin/VKA anticoagulant", "DOAC anticoagulant", "Heparin/LMWH anticoagulant"]), "peptic_ulcer_history", "High", "Blood thinners raise the risk of re-bleeding from an ulcer.", "Ask about stomach protection."),
    (_m(["DOAC anticoagulant"]), lambda c: c.egfr is not None and c.egfr < 30, "High", "DOAC dosing depends on kidney function and some are avoided when eGFR is low.", "Ask your doctor to confirm the dose."),
    (_m(names=["Digoxin", "Lithium carbonate"]), "renal_impairment", "High", "Cleared by the kidneys with a narrow safety margin - levels can climb.", "Ask for a blood-level check."),
    (_m(["Potassium supplement", "Potassium-sparing diuretic"]), "renal_impairment", "High", "Kidney disease reduces potassium removal - high potassium can affect the heart.", "Check potassium regularly."),
    (_m(["Bisphosphonate"]), lambda c: c.egfr is not None and c.egfr < 35, "High", "Oral bisphosphonates are not recommended with low kidney function.", "Ask your doctor about alternatives."),
    (_m(["PDE5 inhibitor"]), "heart_disease", "Moderate", "Sexual-activity and blood-pressure effects need cardiac clearance.", "Never combine with nitrates."),
    (_m(["Beta-2 agonist bronchodilator", "Theophylline/Xanthine"]), "heart_disease", "Moderate", "Can speed up the heart and trigger arrhythmias.", "Report palpitations."),
    (_m(names=["Glyburide"]), "elderly", "High", "Glyburide causes prolonged low blood sugar in older adults.", "Ask about a safer diabetes medicine."),
    (_m(["Sulfonylurea"]), "renal_impairment", "Moderate", "Reduced kidney function prolongs sulfonylurea action - hypoglycemia risk.", "Monitor glucose."),
    (_m(["Opioid"]), "renal_impairment", "Moderate", "Some opioid metabolites accumulate in kidney disease.", "Use lowest dose; watch for drowsiness."),
]


def precautions(meds: list[dict], ctx: Ctx):
    out = []
    for m in meds:
        for spec, cond, level, msg, adv in PRECAUTIONS:
            if not (m["class_name"] in spec["classes"] or m["name"] in spec["names"] or set(m["tags"]) & spec["tags"]):
                continue
            hit = cond(ctx) if callable(cond) else ctx.has(cond)
            if hit:
                label = CONDITIONS.get(cond, {}).get("label") if isinstance(cond, str) else "your kidney function / test results"
                out.append({"drug": m["name"], "condition": label, "level": level, "message": msg, "advice": adv})
    order = {"Critical": 0, "High": 1, "Moderate": 2}
    return sorted(out, key=lambda x: order[x["level"]])


def allergy_alerts(meds: list[dict], allergies: list[dict], kb: KB):
    out = []
    for al in allergies:
        text = norm(al.get("allergen"))
        direct = kb.resolve(text, fuzzy=False)
        key = next((k for k, v in ALLERGENS.items() if any(t in text.split() or t == text for t in v["terms"])), None)
        for m in meds:
            if direct and norm(direct["name"]) == norm(m["name"]):
                out.append({"drug": m["name"], "allergen": al["allergen"], "level": "Critical", "message": f"You have recorded an allergy to {al['allergen']} - this is the same medicine.", "advice": "Do not take it; contact your doctor now."})
            elif key and (m["class_name"] in ALLERGENS[key]["classes"] or m["name"] in ALLERGENS[key]["drugs"]):
                soft = ALLERGENS[key].get("soft")
                out.append({"drug": m["name"], "allergen": al["allergen"], "level": "Moderate" if soft else "High",
                            "message": f"{m['name']} belongs to the group linked to your {ALLERGENS[key]['label']} allergy" + (" (cross-reaction is uncommon but possible)." if soft else "."),
                            "advice": "Ask your doctor or pharmacist to confirm it is safe for you."})
    return out


# ------------------------------------------------------------------ monitoring + diet
MONITOR = [
    (lambda m: m["class_name"] == "Warfarin/VKA anticoagulant", "INR (clotting time)", "Warfarin needs regular INR checks."),
    (lambda m: m["class_name"] in ("DOAC anticoagulant", "Heparin/LMWH anticoagulant"), "Kidney function and blood count", "Anticoagulant dosing depends on kidney function."),
    (lambda m: "hyperkalemia_risk" in m["tags"], "Potassium and creatinine", "Can raise potassium."),
    (lambda m: "hypokalemia_risk" in m["tags"], "Potassium and magnesium", "Can lower potassium."),
    (lambda m: "qt_risk" in m["tags"], "ECG (QTc interval)", "Can prolong the QT interval."),
    (lambda m: m["name"] in ("Digoxin", "Lithium carbonate", "Phenytoin", "Carbamazepine", "Cyclosporine", "Tacrolimus", "Theophylline", "Valproate", "Methotrexate", "Aminophylline"), "Drug blood level", "Narrow safety margin."),
    (lambda m: "hypoglycemia_risk" in m["tags"], "Blood glucose / HbA1c", "Can cause low blood sugar."),
    (lambda m: "bone_marrow_suppression_risk" in m["tags"], "Complete blood count", "Can lower blood counts."),
    (lambda m: m["tags"] and ({"nephrotoxicity_risk", "renal_risk"} & set(m["tags"])), "Kidney function (creatinine / eGFR)", "Can affect the kidneys."),
    (lambda m: m["class_name"] in ("Statin", "Acetaminophen", "Antitubercular (Rifamycin)") or m["name"] in ("Methotrexate", "Valproate"), "Liver function tests", "Can affect the liver."),
    (lambda m: "bradycardia_risk" in m["tags"], "Heart rate and ECG", "Can slow the heart."),
    (lambda m: "hypotension_risk" in m["tags"], "Blood pressure", "Can lower blood pressure."),
    (lambda m: m["name"] == "Levothyroxine", "TSH (6-8 weeks after any change)", "Thyroid dose depends on absorption."),
]


def monitoring(meds):
    agg = {}
    for test_fn, test, why in MONITOR:
        for m in meds:
            if test_fn(m):
                agg.setdefault(test, {"test": test, "reason": why, "drugs": []})["drugs"].append(m["name"])
    return list(agg.values())[:10]


def _cls(meds, *c): return any(m["class_name"] in c for m in meds)
def _drug(meds, *n): return any(m["name"] in n for m in meds)
def _tag(meds, *t): return any(set(m["tags"]) & set(t) for m in meds)


def diet_plan(meds, ctx: Ctx, flagged_diet: list[str]):
    D = {"avoid": [], "limit": [], "keep_consistent": [], "timing": [], "recommended": [], "notes": []}
    seen = set()
    def add(cat, text, why):
        if text not in seen:
            seen.add(text); D[cat].append({"text": text, "why": why})
    c = ctx.has
    if _cls(meds, "Warfarin/VKA anticoagulant"):
        add("keep_consistent", "Leafy greens (palak/spinach, methi, cabbage, broccoli)", "Vitamin K counteracts warfarin - keep the amount steady week to week instead of avoiding it.")
        add("avoid", "Herbal / ayurvedic supplements, ginkgo, garlic or ginger pills, St John's wort - unless your doctor approves", "They can change warfarin's effect unpredictably.")
    if _cls(meds, "Warfarin/VKA anticoagulant", "DOAC anticoagulant", "Heparin/LMWH anticoagulant") or _tag(meds, "bleeding_risk"):
        add("limit", "Alcohol", "Alcohol raises bleeding risk.")
    if _tag(meds, "hyperkalemia_risk") and (c("renal_impairment") or _cls(meds, "ACE inhibitor", "ARB", "Potassium-sparing diuretic", "Potassium supplement", "Direct renin inhibitor")):
        add("limit", "High-potassium foods: banana, tender coconut water, orange, potato, tomato, dried fruit", "Your medicines or kidneys can let potassium build up.")
        add("avoid", "Salt substitutes / 'low-sodium salt' (potassium chloride)", "They are concentrated potassium.")
    if _tag(meds, "hypokalemia_risk") and not c("renal_impairment"):
        add("recommended", "Potassium-rich foods (banana, coconut water, lentils, leafy vegetables) unless your doctor says otherwise", "Diuretics, steroids and bronchodilators can lower potassium.")
    if _drug(meds, "Digoxin") or _cls(meds, "Loop diuretic", "Thiazide diuretic"):
        add("avoid", "Large amounts of licorice (mulethi)", "Licorice lowers potassium and can aggravate heart-rhythm risk.")
    if _cls(meds, "MAOI"):
        add("avoid", "Aged cheese, cured/smoked meats, fermented soy products, sauerkraut, tap beer, overripe fruit", "Tyramine with MAOIs can cause a dangerous blood-pressure surge.")
    if _drug(meds, "Simvastatin", "Lovastatin", "Atorvastatin") or _cls(meds, "Immunosuppressant (calcineurin inhibitor)", "Dihydropyridine CCB", "PDE5 inhibitor", "HIV protease inhibitor"):
        add("avoid", "Grapefruit and pomelo (chakotra) juice or fruit", "They block CYP3A4 and raise levels of your medicine.")
    if _drug(meds, "Levothyroxine"):
        add("timing", "Take levothyroxine on an empty stomach, 30-60 minutes before breakfast; keep calcium, iron, antacids and soy at least 4 hours away", "These bind levothyroxine and reduce absorption.")
    if _cls(meds, "Bisphosphonate"):
        add("timing", "Take with plain water only, stay upright 30-60 minutes, and keep dairy/calcium away from the dose", "Absorption is very low and easily blocked.")
    if _cls(meds, "Tetracycline", "Fluoroquinolone"):
        add("timing", "Keep milk, curd, paneer, calcium, iron and antacids 2-4 hours away from the antibiotic", "Calcium and iron bind these antibiotics.")
    if _cls(meds, "Iron supplement"):
        add("timing", "Take iron with vitamin C (e.g. lemon water); avoid tea/coffee near the dose; separate from antacids and levothyroxine", "Improves absorption and avoids binding.")
    if _cls(meds, "Sulfonylurea", "Insulin", "SGLT2 inhibitor", "GLP-1 agonist"):
        add("keep_consistent", "Regular meal timing - do not skip meals", "Skipped meals with these medicines can cause low blood sugar.")
        add("recommended", "Carry a fast sugar source (glucose tablets, juice)", "For quick treatment of hypoglycemia.")
    if _cls(meds, "Metformin"):
        add("timing", "Take metformin with meals", "Reduces stomach upset.")
        add("limit", "Alcohol", "Heavy drinking with metformin raises lactic acidosis risk.")
    if _cls(meds, "NSAID"):
        add("timing", "Take NSAIDs with food", "Lowers stomach irritation.")
    if _cls(meds, "Opioid"):
        add("recommended", "Fibre and plenty of fluids", "Opioids cause constipation.")
    if _tag(meds, "cns_depressant"):
        add("avoid", "Alcohol", "Adds to drowsiness and slows breathing.")
    if _cls(meds, "Acetaminophen"):
        add("limit", "Alcohol; keep acetaminophen within the daily maximum", "Liver protection.")
    if _cls(meds, "Corticosteroid"):
        add("limit", "Sugar, sweets and salty foods during steroid courses", "Steroids raise blood sugar, blood pressure and fluid retention.")
        add("recommended", "Calcium and vitamin D-rich foods", "Protects bones.")
    if _drug(meds, "Lithium carbonate"):
        add("keep_consistent", "Salt and fluid intake - avoid dehydration and crash diets", "Sodium and fluid changes alter lithium levels.")
    if _cls(meds, "Theophylline/Xanthine"):
        add("keep_consistent", "Caffeine intake (tea, coffee, cola)", "Caffeine competes with theophylline.")
    if _tag(meds, "qt_risk"):
        add("limit", "Energy drinks and very high caffeine", "Can add to heart-rhythm effects.")
        add("keep_consistent", "Balanced electrolytes (fruit, vegetables, adequate fluids)", "Low potassium/magnesium raises QT risk.")
    if c("diabetes"):
        add("limit", "Sugary drinks, sweets and refined carbohydrates; prefer whole grains and millets", "Supports blood-sugar control.")
    if c("hypertension", "heart_disease", "heart_failure") or c("renal_impairment"):
        add("limit", "Salt - pickles (achar), papad, processed and packaged foods", "Lower sodium helps blood pressure, fluid balance and kidneys (aim for under 5 g salt/day unless told otherwise).")
    if c("hepatic_impairment"):
        add("avoid", "Alcohol and unprescribed herbal/ayurvedic preparations", "Many are processed by the liver and some are toxic to it.")
    if c("renal_impairment"):
        add("notes", "Ask your nephrologist or dietitian about personal potassium, phosphorus and protein limits.", "Needs depend on your kidney stage.")
    if c("osteoporosis"):
        add("recommended", "Calcium and vitamin D-rich foods and safe sunlight", "Bone health (mind the timing rules for bone medicines).")
    if c("pregnancy"):
        add("avoid", "Alcohol; ask before using any herbal remedy", "Protects the baby.")
    if ctx.alcohol in ("heavy", "moderate"):
        add("limit", "Alcohol", "You reported regular alcohol use, which interacts with many medicines.")
    for t in flagged_diet:
        if t and not t.lower().startswith(("no specific", "no diet", "n/a")):
            if not any(t.lower()[:28] in x["text"].lower() or x["text"].lower()[:28] in t.lower() for cat in D.values() for x in cat):
                add("notes", t, "From a flagged interaction.")
    return {k: v for k, v in D.items() if v}


# ------------------------------------------------------------------ main entry
def analyze(kb: KB, profile: dict, meds: list[dict], conditions: list[dict], allergies: list[dict]) -> dict:
    ctx = Ctx(profile, conditions)
    active = [m for m in meds if m.get("status", "active") == "active"]
    recognised, unassessed, seen = [], [], set()
    for m in active:
        d = kb.resolve(m["name"])
        if d and d["name"] not in seen:
            seen.add(d["name"]); recognised.append({**d, "entered_as": m["name"], "dose": m.get("dose"), "frequency": m.get("frequency")})
        elif not d:
            unassessed.append(m["name"])
    n = len(recognised) + len(unassessed)

    confirmed, possible = [], []
    for a, b in itertools.combinations(recognised, 2):
        tags = set(a["tags"]) | set(b["tags"])
        row = kb.pair(a["name"], b["name"])
        if row:
            score, factors = personalise(BASE[row["severity"]], tags, ctx, n)
            rec = {"drug_a": a["name"], "drug_b": b["name"], "base_severity": row["severity"], "score": score, "level": level_for(score), "source": "curated_rule", "confidence": 1.0,
                   "mechanism": row["mechanism"], "effect": row["effect"], "management": row["management"], "diet_advice": row["diet_advice"], "factors": factors}
            rec["summary"] = f"{a['name']} with {b['name']}: {row['effect'].rstrip('.')}. " + (f"For you this is rated {rec['level'].lower()} because of {', '.join(f['label'] for f in factors[:3])}." if factors else f"Rated {rec['level'].lower()} for a typical patient.")
            confirmed.append(rec)
        elif kb.ml:
            sev, conf = kb.ml.predict(a, b)
            if sev in ("Moderate", "Major") and conf >= 0.75:
                score, factors = personalise(int(BASE[sev] * 0.6), tags, ctx, n)
                score = min(score, 54)
                possible.append({"drug_a": a["name"], "drug_b": b["name"], "base_severity": sev, "score": score, "level": level_for(score), "source": "model_estimate", "confidence": round(conf, 2),
                                 "mechanism": "Estimated from shared pharmacological properties; no curated record exists for this exact pair.",
                                 "effect": "Possible interaction - unverified", "management": "Ask your pharmacist to verify this combination.", "diet_advice": "", "factors": factors,
                                 "summary": f"{a['name']} and {b['name']} share properties that may interact (unverified model estimate)."})
    confirmed.sort(key=lambda r: -r["score"]); possible.sort(key=lambda r: -r["score"])
    pre = precautions(recognised, ctx)
    alg = allergy_alerts(recognised, allergies, kb)
    top = max([r["score"] for r in confirmed] + [LEVEL_SCORE[x["level"]] for x in pre + alg] + [0])
    extra = sum(1 for r in confirmed if r["score"] >= 55) + len(pre) // 2 + len(alg)
    overall_score = min(100, top + max(0, extra - 1) * 2) if top else 0
    lvl = level_for(overall_score) if top else "None"
    counts = {k: sum(1 for r in confirmed if r["level"] == k) for k in ("Critical", "High", "Moderate", "Low")}
    headline = {"Critical": "Urgent review recommended - please speak to your doctor or pharmacist today.",
                "High": "Important issues found - discuss these with your doctor before your next dose where possible.",
                "Moderate": "Some combinations need caution and monitoring.",
                "Low": "Only minor issues found.", "None": "No interactions found in our database for your current medicines."}[lvl]
    qs = []
    for r in confirmed[:3]:
        if r["score"] >= 55: qs.append(f"Is it safe for me to keep taking {r['drug_a']} together with {r['drug_b']}? Is there a safer alternative or a dose change?")
    for p in pre[:2]: qs.append(f"{p['drug']} and {p['condition'].lower() if p['condition'] else 'my health condition'}: should this medicine be changed?")
    for u in unassessed[:3]: qs.append(f"Can you check {u} for interactions? It is not in Sanjeevani AI's database.")
    return {
        "overall": {"score": overall_score, "level": lvl, "headline": headline, "counts": counts, "n_medicines": n, "n_assessed": len(recognised)},
        "patient": {"age": ctx.age, "sex": ctx.sex, "bmi": ctx.bmi, "egfr": ctx.egfr, "egfr_estimated": ctx.egfr_estimated, "derived_conditions": ctx.derived,
                    "conditions": sorted(ctx.keys), "alcohol": ctx.alcohol, "smoker": ctx.smoker},
        "medicines": [{"name": m["name"], "class": m["class_name"], "entered_as": m["entered_as"]} for m in recognised],
        "interactions": confirmed, "possible_interactions": possible,
        "precautions": pre, "allergy_alerts": alg, "unassessed": unassessed,
        "monitoring": monitoring(recognised), "diet": diet_plan(recognised, ctx, [r["diet_advice"] for r in confirmed[:6] if r["score"] >= 55][:3]),
        "questions_for_doctor": qs[:6], "disclaimer": DISCLAIMER,
    }
