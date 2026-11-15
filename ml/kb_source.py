"""
Builds a curated, research-scale drug-drug interaction (DDI) dataset from
established clinical pharmacology knowledge (drug classes, mechanisms,
severity grading, management/diet guidance). This is NOT a scrape of any
proprietary database (DrugBank/Micromedex/Lexicomp) -- it is hand-authored
class-level pharmacology encoded as data, expanded to drug level.

Scale: ~40 drug classes x ~6 drugs each = ~240 drugs; class-level interaction
rules are authored for the clinically important pairs (~95 class-pairs),
then expanded to drug-level pairs (~9,000 labeled pairs after expansion +
negative sampling of non-interacting pairs).
"""
import json
import random
import itertools

random.seed(42)

# ---------------------------------------------------------------------------
# 1. Drug classes -> representative real drugs + pharmacologic tags
# ---------------------------------------------------------------------------
CLASSES = {
    "Warfarin/VKA anticoagulant": {
        "drugs": ["Warfarin", "Acenocoumarol", "Phenprocoumon"],
        "tags": ["anticoagulant", "cyp2c9_substrate", "narrow_therapeutic_index"],
    },
    "DOAC anticoagulant": {
        "drugs": ["Apixaban", "Rivaroxaban", "Dabigatran", "Edoxaban"],
        "tags": ["anticoagulant", "pgp_substrate", "renal_clearance"],
    },
    "Antiplatelet": {
        "drugs": ["Aspirin", "Clopidogrel", "Ticagrelor", "Prasugrel"],
        "tags": ["antiplatelet", "bleeding_risk"],
    },
    "NSAID": {
        "drugs": ["Ibuprofen", "Naproxen", "Diclofenac", "Indomethacin", "Celecoxib"],
        "tags": ["nsaid", "gi_risk", "renal_risk", "bleeding_risk"],
    },
    "SSRI": {
        "drugs": ["Fluoxetine", "Sertraline", "Citalopram", "Paroxetine", "Escitalopram"],
        "tags": ["serotonergic", "cyp2d6_inhibitor", "qt_risk"],
    },
    "SNRI": {
        "drugs": ["Venlafaxine", "Duloxetine", "Desvenlafaxine"],
        "tags": ["serotonergic"],
    },
    "MAOI": {
        "drugs": ["Phenelzine", "Tranylcypromine", "Selegiline"],
        "tags": ["serotonergic", "hypertensive_crisis_risk", "tyramine_interaction"],
    },
    "Triptan": {
        "drugs": ["Sumatriptan", "Rizatriptan", "Zolmitriptan"],
        "tags": ["serotonergic", "vasoconstrictor"],
    },
    "Statin": {
        "drugs": ["Simvastatin", "Atorvastatin", "Lovastatin", "Rosuvastatin", "Pravastatin"],
        "tags": ["cyp3a4_substrate", "myopathy_risk"],
    },
    "Macrolide antibiotic": {
        "drugs": ["Clarithromycin", "Erythromycin", "Azithromycin"],
        "tags": ["cyp3a4_inhibitor", "qt_risk"],
    },
    "Azole antifungal": {
        "drugs": ["Ketoconazole", "Itraconazole", "Fluconazole", "Voriconazole"],
        "tags": ["cyp3a4_inhibitor", "qt_risk"],
    },
    "ACE inhibitor": {
        "drugs": ["Lisinopril", "Enalapril", "Ramipril", "Captopril"],
        "tags": ["raas", "hyperkalemia_risk", "renal_risk"],
    },
    "ARB": {
        "drugs": ["Losartan", "Valsartan", "Irbesartan", "Candesartan"],
        "tags": ["raas", "hyperkalemia_risk", "renal_risk"],
    },
    "Potassium-sparing diuretic": {
        "drugs": ["Spironolactone", "Eplerenone", "Amiloride"],
        "tags": ["hyperkalemia_risk"],
    },
    "Loop diuretic": {
        "drugs": ["Furosemide", "Bumetanide", "Torsemide"],
        "tags": ["hypokalemia_risk", "ototoxicity_risk", "renal_risk"],
    },
    "Thiazide diuretic": {
        "drugs": ["Hydrochlorothiazide", "Chlorthalidone", "Indapamide"],
        "tags": ["hypokalemia_risk", "qt_risk"],
    },
    "Potassium supplement": {
        "drugs": ["Potassium chloride"],
        "tags": ["hyperkalemia_risk"],
    },
    "Digoxin": {
        "drugs": ["Digoxin"],
        "tags": ["pgp_substrate", "narrow_therapeutic_index", "arrhythmia_risk"],
    },
    "Beta blocker": {
        "drugs": ["Metoprolol", "Atenolol", "Propranolol", "Bisoprolol", "Carvedilol"],
        "tags": ["bradycardia_risk", "cyp2d6_substrate"],
    },
    "Non-dihydropyridine CCB": {
        "drugs": ["Verapamil", "Diltiazem"],
        "tags": ["cyp3a4_inhibitor", "bradycardia_risk"],
    },
    "Dihydropyridine CCB": {
        "drugs": ["Amlodipine", "Nifedipine", "Felodipine"],
        "tags": ["cyp3a4_substrate", "hypotension_risk"],
    },
    "Benzodiazepine": {
        "drugs": ["Diazepam", "Alprazolam", "Lorazepam", "Clonazepam", "Midazolam"],
        "tags": ["cns_depressant", "cyp3a4_substrate"],
    },
    "Opioid": {
        "drugs": ["Morphine", "Oxycodone", "Tramadol", "Fentanyl", "Codeine", "Hydrocodone"],
        "tags": ["cns_depressant", "respiratory_depression_risk", "serotonergic_partial"],
    },
    "Z-drug hypnotic": {
        "drugs": ["Zolpidem", "Zopiclone", "Eszopiclone"],
        "tags": ["cns_depressant"],
    },
    "Antipsychotic (QT risk)": {
        "drugs": ["Haloperidol", "Ziprasidone", "Quetiapine", "Risperidone"],
        "tags": ["qt_risk", "cns_depressant"],
    },
    "Antiepileptic (enzyme inducer)": {
        "drugs": ["Carbamazepine", "Phenytoin", "Phenobarbital"],
        "tags": ["cyp3a4_inducer", "cyp2c9_inducer"],
    },
    "Antiepileptic (other)": {
        "drugs": ["Valproate", "Levetiracetam", "Lamotrigine"],
        "tags": ["hepatic_metabolism"],
    },
    "Metformin": {
        "drugs": ["Metformin"],
        "tags": ["renal_clearance", "lactic_acidosis_risk"],
    },
    "Sulfonylurea": {
        "drugs": ["Glipizide", "Glyburide", "Glimepiride"],
        "tags": ["hypoglycemia_risk", "cyp2c9_substrate"],
    },
    "Insulin": {
        "drugs": ["Insulin glargine", "Insulin lispro", "Insulin aspart", "Regular insulin"],
        "tags": ["hypoglycemia_risk"],
    },
    "Direct renin inhibitor": {
        "drugs": ["Aliskiren"],
        "tags": ["raas", "hyperkalemia_risk"],
    },
    "Corticosteroid": {
        "drugs": ["Prednisone", "Dexamethasone", "Hydrocortisone", "Methylprednisolone"],
        "tags": ["hyperglycemia_risk", "gi_risk", "immunosuppressant", "hypokalemia_risk"],
    },
    "Immunosuppressant (calcineurin inhibitor)": {
        "drugs": ["Cyclosporine", "Tacrolimus"],
        "tags": ["cyp3a4_substrate", "nephrotoxicity_risk", "narrow_therapeutic_index"],
    },
    "PDE5 inhibitor": {
        "drugs": ["Sildenafil", "Tadalafil", "Vardenafil"],
        "tags": ["vasodilator", "hypotension_risk"],
    },
    "Nitrate": {
        "drugs": ["Nitroglycerin", "Isosorbide mononitrate", "Isosorbide dinitrate"],
        "tags": ["vasodilator", "hypotension_risk"],
    },
    "Proton pump inhibitor": {
        "drugs": ["Omeprazole", "Esomeprazole", "Pantoprazole", "Lansoprazole"],
        "tags": ["cyp2c19_inhibitor", "gastric_ph_dependent_absorption"],
    },
    "Fluoroquinolone": {
        "drugs": ["Ciprofloxacin", "Levofloxacin", "Moxifloxacin"],
        "tags": ["qt_risk", "cyp1a2_inhibitor", "chelation_risk"],
    },
    "Tetracycline": {
        "drugs": ["Doxycycline", "Tetracycline", "Minocycline"],
        "tags": ["chelation_risk"],
    },
    "Levothyroxine": {
        "drugs": ["Levothyroxine"],
        "tags": ["narrow_therapeutic_index", "chelation_risk", "absorption_sensitive"],
    },
    "Lithium": {
        "drugs": ["Lithium carbonate"],
        "tags": ["narrow_therapeutic_index", "renal_clearance"],
    },
    "Methotrexate": {
        "drugs": ["Methotrexate"],
        "tags": ["renal_clearance", "narrow_therapeutic_index", "bone_marrow_suppression_risk"],
    },
    "Fibrate": {
        "drugs": ["Gemfibrozil", "Fenofibrate"],
        "tags": ["myopathy_risk", "cyp2c8_inhibitor"],
    },
    "Grapefruit (food)": {
        "drugs": ["Grapefruit juice"],
        "tags": ["cyp3a4_inhibitor_food"],
    },
    "Vitamin K-rich foods (food)": {
        "drugs": ["Leafy green vegetables"],
        "tags": ["vitamin_k_source"],
    },
    "Tyramine-rich foods (food)": {
        "drugs": ["Aged cheese / cured meats"],
        "tags": ["tyramine_source"],
    },
    # --- Expansion: oncology, cardiology, respiratory, GI, bone, thyroid, infectious, antivirals ---
    "Heparin/LMWH anticoagulant": {
        "drugs": ["Heparin", "Enoxaparin", "Dalteparin", "Fondaparinux"],
        "tags": ["anticoagulant", "bleeding_risk"],
    },
    "Antiarrhythmic (Class III)": {
        "drugs": ["Amiodarone", "Dronedarone", "Sotalol"],
        "tags": ["qt_risk", "cyp3a4_inhibitor", "cyp2d6_inhibitor", "bradycardia_risk"],
    },
    "Theophylline/Xanthine": {
        "drugs": ["Theophylline", "Aminophylline"],
        "tags": ["cyp1a2_substrate", "narrow_therapeutic_index", "arrhythmia_risk"],
    },
    "Beta-2 agonist bronchodilator": {
        "drugs": ["Albuterol", "Salmeterol", "Formoterol"],
        "tags": ["hypokalemia_risk", "arrhythmia_risk"],
    },
    "H2 receptor antagonist": {
        "drugs": ["Cimetidine", "Ranitidine", "Famotidine"],
        "tags": ["cyp1a2_inhibitor", "cyp3a4_inhibitor", "gastric_ph_dependent_absorption"],
    },
    "Bisphosphonate": {
        "drugs": ["Alendronate", "Risedronate", "Ibandronate", "Zoledronic acid"],
        "tags": ["chelation_risk", "gi_risk", "absorption_sensitive"],
    },
    "Antithyroid": {
        "drugs": ["Methimazole", "Propylthiouracil"],
        "tags": ["bone_marrow_suppression_risk", "hepatic_metabolism"],
    },
    "Gout agent": {
        "drugs": ["Allopurinol", "Febuxostat", "Colchicine"],
        "tags": ["cyp3a4_substrate", "bone_marrow_suppression_risk", "myopathy_risk"],
    },
    "HIV protease inhibitor": {
        "drugs": ["Ritonavir", "Lopinavir", "Atazanavir", "Darunavir"],
        "tags": ["cyp3a4_inhibitor", "pgp_inhibitor", "narrow_therapeutic_index"],
    },
    "Antitubercular (Rifamycin)": {
        "drugs": ["Rifampin", "Rifabutin"],
        "tags": ["cyp3a4_inducer", "cyp2c9_inducer", "hepatic_metabolism"],
    },
    "Chemotherapy - Vinca alkaloid": {
        "drugs": ["Vincristine", "Vinblastine"],
        "tags": ["cyp3a4_substrate", "narrow_therapeutic_index", "bone_marrow_suppression_risk"],
    },
    "Chemotherapy - Fluoropyrimidine": {
        "drugs": ["5-Fluorouracil", "Capecitabine"],
        "tags": ["bone_marrow_suppression_risk", "narrow_therapeutic_index"],
    },
    "Tamoxifen": {
        "drugs": ["Tamoxifen"],
        "tags": ["cyp2d6_substrate", "narrow_therapeutic_index"],
    },
    "First-gen antihistamine": {
        "drugs": ["Diphenhydramine", "Chlorpheniramine", "Hydroxyzine"],
        "tags": ["cns_depressant", "anticholinergic_risk"],
    },
    "Tricyclic antidepressant": {
        "drugs": ["Amitriptyline", "Nortriptyline", "Imipramine"],
        "tags": ["serotonergic", "qt_risk", "anticholinergic_risk", "cyp2d6_substrate"],
    },
    "Antiemetic (5-HT3 antagonist)": {
        "drugs": ["Ondansetron", "Granisetron"],
        "tags": ["qt_risk", "serotonergic"],
    },
    "Muscle relaxant": {
        "drugs": ["Cyclobenzaprine", "Baclofen", "Tizanidine"],
        "tags": ["cns_depressant", "serotonergic_partial"],
    },
    "Combined oral contraceptive": {
        "drugs": ["Ethinylestradiol/Levonorgestrel", "Ethinylestradiol/Norethindrone"],
        "tags": ["cyp3a4_substrate", "thrombosis_risk"],
    },
    # --- Expansion round 2: broader primary-care / chronic-disease coverage ---
    "Second-gen antihistamine": {
        "drugs": ["Cetirizine", "Loratadine", "Fexofenadine"],
        "tags": ["cyp3a4_substrate"],
    },
    "Nasal decongestant": {
        "drugs": ["Pseudoephedrine", "Phenylephrine"],
        "tags": ["hypertensive_crisis_risk", "arrhythmia_risk"],
    },
    "Antiviral (Herpes)": {
        "drugs": ["Acyclovir", "Valacyclovir", "Famciclovir"],
        "tags": ["renal_clearance", "nephrotoxicity_risk"],
    },
    "SGLT2 inhibitor": {
        "drugs": ["Empagliflozin", "Dapagliflozin", "Canagliflozin"],
        "tags": ["renal_clearance", "hypoglycemia_risk"],
    },
    "GLP-1 agonist": {
        "drugs": ["Semaglutide", "Liraglutide", "Dulaglutide"],
        "tags": ["hypoglycemia_risk", "gi_risk"],
    },
    "Antacid": {
        "drugs": ["Aluminum hydroxide", "Magnesium hydroxide", "Calcium carbonate"],
        "tags": ["chelation_risk", "gastric_ph_dependent_absorption"],
    },
    "Iron supplement": {
        "drugs": ["Ferrous sulfate", "Ferrous gluconate"],
        "tags": ["chelation_risk"],
    },
    "Anticholinergic (overactive bladder)": {
        "drugs": ["Oxybutynin", "Tolterodine", "Solifenacin"],
        "tags": ["anticholinergic_risk", "cns_depressant"],
    },
    "Glaucoma agent (topical beta blocker)": {
        "drugs": ["Timolol"],
        "tags": ["bradycardia_risk", "cyp2d6_substrate"],
    },
    "Antipsychotic (atypical, metabolic risk)": {
        "drugs": ["Olanzapine", "Clozapine"],
        "tags": ["cns_depressant", "hyperglycemia_risk", "qt_risk"],
    },
}

# ---------------------------------------------------------------------------
# 2. Class-pair interaction rules: (classA, classB) -> mechanism/severity/mgmt
# ---------------------------------------------------------------------------
RULES = [
    ("Warfarin/VKA anticoagulant", "NSAID", "Additive bleeding risk; NSAIDs impair platelet function and cause GI mucosal injury while warfarin reduces clotting factor synthesis.", "Major", "GI/intracranial bleeding", "Avoid combination; if unavoidable use lowest NSAID dose + PPI, monitor INR closely.", "Limit alcohol; avoid vitamin K intake swings; watch for bruising/black stools."),
    ("Warfarin/VKA anticoagulant", "Antiplatelet", "Combined inhibition of coagulation cascade and platelet aggregation.", "Major", "Bleeding", "Reserve for specific cardiac indications with close monitoring; use lowest effective doses.", "Maintain consistent vitamin K intake; avoid NSAIDs/alcohol."),
    ("Warfarin/VKA anticoagulant", "Macrolide antibiotic", "CYP3A4/CYP2C9 inhibition slows warfarin metabolism, raising INR.", "Major", "Increased INR, bleeding", "Check INR 3-5 days after starting/stopping; consider azithromycin (less interaction).", "Maintain steady vitamin K intake during antibiotic course."),
    ("Warfarin/VKA anticoagulant", "Azole antifungal", "Strong CYP2C9/3A4 inhibition markedly raises warfarin levels.", "Major", "Increased INR, bleeding", "Reduce warfarin dose empirically and monitor INR frequently.", "Maintain steady vitamin K intake."),
    ("Warfarin/VKA anticoagulant", "Antiepileptic (enzyme inducer)", "Enzyme induction accelerates warfarin clearance, lowering INR.", "Moderate", "Subtherapeutic anticoagulation, clot risk", "Monitor INR closely on initiation/discontinuation; adjust dose.", "No specific diet change beyond consistent vitamin K intake."),
    ("Warfarin/VKA anticoagulant", "Vitamin K-rich foods (food)", "Dietary vitamin K directly antagonizes warfarin's mechanism.", "Moderate", "Reduced anticoagulant effect if intake spikes", "Keep vitamin K intake consistent week to week rather than avoiding it entirely.", "Consistent, moderate intake of leafy greens (kale, spinach, broccoli); avoid large sudden changes."),
    ("Warfarin/VKA anticoagulant", "Fluoroquinolone", "CYP enzyme inhibition and gut flora suppression (reducing vitamin K synthesis) raise INR.", "Moderate", "Increased INR", "Monitor INR during and after antibiotic course.", "Maintain steady vitamin K intake."),
    ("DOAC anticoagulant", "Antiplatelet", "Combined anticoagulant + antiplatelet effect increases bleeding risk.", "Major", "Bleeding", "Use only when clinically indicated (e.g. post-stent) with shortest duration.", "Avoid excess alcohol; report unusual bruising/bleeding."),
    ("DOAC anticoagulant", "Azole antifungal", "Strong P-glycoprotein/CYP3A4 inhibition raises DOAC plasma levels.", "Major", "Bleeding", "Consider dose reduction or alternative antifungal; avoid with strong inhibitors + renal impairment.", "No specific diet change; report bleeding symptoms."),
    ("DOAC anticoagulant", "NSAID", "Additive bleeding risk from GI mucosal injury and platelet effects.", "Moderate", "GI bleeding", "Use PPI co-therapy if NSAID needed; prefer acetaminophen for pain.", "Avoid alcohol; monitor for GI symptoms."),
    ("DOAC anticoagulant", "Antiepileptic (enzyme inducer)", "Enzyme induction lowers DOAC plasma concentration.", "Moderate", "Reduced anticoagulant efficacy", "Consider alternative anticoagulant or antiepileptic if long-term co-use needed.", "No specific diet change."),
    ("Antiplatelet", "NSAID", "Additive antiplatelet/GI mucosal injury effect.", "Moderate", "GI bleeding", "Use PPI co-therapy; minimize NSAID duration.", "Avoid alcohol; take NSAID with food."),
    ("Antiplatelet", "Proton pump inhibitor", "Omeprazole/esomeprazole inhibit CYP2C19-mediated activation of clopidogrel, reducing efficacy.", "Moderate", "Reduced antiplatelet effect (clopidogrel specifically)", "Prefer pantoprazole (less CYP2C19 interaction) if PPI required with clopidogrel.", "No specific diet change."),
    ("SSRI", "MAOI", "Excess synaptic serotonin from combined reuptake inhibition and breakdown inhibition.", "Major", "Serotonin syndrome (agitation, hyperthermia, clonus)", "Contraindicated; require 2-5 week washout when switching between classes.", "Avoid tyramine-rich foods only relevant to MAOI itself, not this combo; seek care for fever/tremor/agitation."),
    ("SSRI", "SNRI", "Combined serotonin reuptake inhibition.", "Moderate", "Serotonin syndrome risk, mostly with dose stacking", "Avoid unless under specialist supervision during cross-titration.", "Monitor for agitation, sweating, tremor."),
    ("SSRI", "Triptan", "Additive serotonergic activity at 5-HT receptors.", "Moderate", "Serotonin syndrome (usually mild)", "Can often be combined with monitoring; counsel on symptoms.", "Monitor for restlessness, tremor, diarrhea after triptan dosing."),
    ("SSRI", "Opioid", "Tramadol/fentanyl have serotonergic activity; combined with SSRI raises serotonin syndrome risk.", "Moderate", "Serotonin syndrome, especially with tramadol", "Prefer opioids with minimal serotonergic activity (e.g., oxycodone) when possible.", "Avoid alcohol; monitor mental status."),
    ("SSRI", "Antiplatelet", "SSRIs impair platelet serotonin uptake, reducing platelet aggregation; additive to antiplatelet drugs.", "Moderate", "Increased bleeding risk", "Monitor for bruising/GI bleeding; consider gastroprotection.", "Avoid alcohol and NSAIDs if possible."),
    ("SSRI", "NSAID", "SSRI-impaired platelet function plus NSAID GI mucosal injury.", "Moderate", "GI bleeding", "Consider PPI co-therapy if long-term NSAID needed.", "Take NSAID with food; avoid alcohol."),
    ("MAOI", "Opioid", "Risk of severe serotonin syndrome or hypertensive crisis, especially with meperidine/tramadol.", "Major", "Serotonin syndrome, hypertensive crisis", "Contraindicated with meperidine/tramadol/fentanyl class overlap; use extreme caution.", "Strict low-tyramine diet required with MAOIs regardless of opioid co-use."),
    ("MAOI", "Tyramine-rich foods (food)", "MAOIs block tyramine breakdown; dietary tyramine triggers massive norepinephrine release.", "Major", "Hypertensive crisis", "Strict avoidance required while on MAOI therapy and 2 weeks after stopping.", "Avoid aged cheese, cured/fermented meats, tap beer, soy sauce, sauerkraut, overripe fruit."),
    ("MAOI", "Triptan", "Combined serotonergic effect; also MAOIs slow triptan metabolism.", "Major", "Serotonin syndrome", "Avoid combination; use non-triptan migraine therapy if on MAOI.", "Low-tyramine diet required for MAOI regardless."),
    ("Statin", "Macrolide antibiotic", "CYP3A4 inhibition raises statin levels substantially.", "Major", "Myopathy, rhabdomyolysis", "Hold statin during short antibiotic course, or switch to azithromycin/pravastatin (less CYP3A4-dependent).", "Report unexplained muscle pain, dark urine."),
    ("Statin", "Azole antifungal", "Strong CYP3A4 inhibition raises statin exposure.", "Major", "Myopathy, rhabdomyolysis", "Suspend statin during antifungal course or use fluvastatin/pravastatin.", "Report muscle pain/weakness immediately."),
    ("Statin", "Non-dihydropyridine CCB", "Verapamil/diltiazem inhibit CYP3A4, raising statin levels.", "Moderate", "Myopathy risk", "Cap simvastatin/lovastatin dose per label; consider alternative statin.", "Report muscle symptoms; limit grapefruit juice."),
    ("Statin", "Fibrate", "Additive myopathy risk; gemfibrozil also inhibits statin glucuronidation.", "Major", "Rhabdomyolysis", "Avoid gemfibrozil + statin combination; fenofibrate is a safer pairing if needed.", "Report dark urine, severe muscle pain."),
    ("Statin", "Grapefruit (food)", "Grapefruit furanocoumarins inhibit intestinal CYP3A4, raising statin absorption.", "Moderate", "Increased statin exposure, myopathy risk", "Avoid grapefruit juice with CYP3A4-dependent statins (simvastatin, lovastatin, atorvastatin).", "Avoid grapefruit/grapefruit juice; pravastatin/rosuvastatin are lower-risk alternatives."),
    ("Immunosuppressant (calcineurin inhibitor)", "Statin", "CYP3A4 competition raises statin levels.", "Moderate", "Myopathy risk", "Use low statin doses; monitor CK.", "Report muscle pain; avoid grapefruit juice."),
    ("Immunosuppressant (calcineurin inhibitor)", "Macrolide antibiotic", "CYP3A4 inhibition raises cyclosporine/tacrolimus levels.", "Major", "Nephrotoxicity, elevated drug levels", "Monitor trough levels closely; adjust dose.", "Maintain consistent grapefruit avoidance and fluid intake."),
    ("Immunosuppressant (calcineurin inhibitor)", "Grapefruit (food)", "Intestinal CYP3A4 inhibition raises calcineurin inhibitor absorption.", "Major", "Nephrotoxicity, elevated drug levels", "Avoid grapefruit products entirely on these medications.", "Avoid grapefruit and grapefruit juice completely."),
    ("ACE inhibitor", "Potassium-sparing diuretic", "Both reduce potassium excretion via RAAS/aldosterone pathway suppression.", "Major", "Hyperkalemia", "Monitor potassium and renal function within 1 week of starting; avoid triple combo with ARB.", "Limit high-potassium foods (bananas, oranges, potatoes, salt substitutes with KCl)."),
    ("ACE inhibitor", "ARB", "Dual RAAS blockade compounds hyperkalemia and renal risk without added benefit in most patients.", "Major", "Hyperkalemia, acute kidney injury", "Generally avoid combination therapy; use one RAAS agent.", "Limit high-potassium foods; ensure adequate hydration."),
    ("ACE inhibitor", "Potassium supplement", "Reduced potassium excretion plus exogenous potassium load.", "Major", "Hyperkalemia", "Avoid routine potassium supplementation unless levels are monitored closely.", "Avoid salt substitutes containing potassium chloride."),
    ("ACE inhibitor", "NSAID", "NSAIDs reduce renal prostaglandin-mediated perfusion; combined with ACEi reduces GFR (\"triple whammy\" with diuretics).", "Moderate", "Acute kidney injury, reduced antihypertensive effect", "Avoid chronic NSAID use; monitor renal function if combined, especially with diuretics.", "Stay well hydrated; limit added salt."),
    ("ARB", "Potassium-sparing diuretic", "Additive potassium retention.", "Major", "Hyperkalemia", "Monitor potassium closely; avoid in renal impairment.", "Limit high-potassium foods and potassium-based salt substitutes."),
    ("ARB", "NSAID", "Reduced renal perfusion compensation is blunted by both drugs.", "Moderate", "Acute kidney injury", "Monitor renal function with chronic use; stay hydrated.", "Adequate hydration; limit added salt."),
    ("Direct renin inhibitor", "ACE inhibitor", "Dual RAAS inhibition; aliskiren + ACEi contraindicated especially in diabetes/renal impairment.", "Major", "Hyperkalemia, hypotension, renal injury", "Avoid combination, particularly in diabetic or renally impaired patients.", "Limit high-potassium foods."),
    ("Digoxin", "Loop diuretic", "Diuretic-induced hypokalemia increases myocardial sensitivity to digoxin toxicity.", "Major", "Digoxin toxicity (arrhythmia, visual changes, nausea)", "Monitor potassium and digoxin levels; supplement potassium if low.", "Ensure adequate dietary potassium; avoid excess licorice (can worsen hypokalemia)."),
    ("Digoxin", "Thiazide diuretic", "Diuretic-induced hypokalemia/hypomagnesemia sensitizes to digoxin toxicity.", "Major", "Digoxin toxicity", "Monitor electrolytes and digoxin level periodically.", "Adequate potassium-rich foods unless contraindicated."),
    ("Digoxin", "Non-dihydropyridine CCB", "Verapamil inhibits P-glycoprotein, raising digoxin levels; also additive AV nodal block.", "Major", "Digoxin toxicity, bradycardia", "Check digoxin level and reduce dose if combined; monitor heart rate.", "No specific diet change; report dizziness/palpitations."),
    ("Digoxin", "Macrolide antibiotic", "Some macrolides alter gut flora that normally degrades digoxin, raising levels.", "Moderate", "Digoxin toxicity", "Monitor digoxin level if prolonged antibiotic course needed.", "Report nausea, visual disturbances, palpitations."),
    ("Beta blocker", "Non-dihydropyridine CCB", "Additive suppression of AV node conduction and myocardial contractility.", "Major", "Severe bradycardia, heart block, heart failure", "Avoid IV combination; use oral combination cautiously with monitoring.", "No specific diet change; report dizziness/fainting."),
    ("Beta blocker", "Digoxin", "Additive negative chronotropic effect.", "Moderate", "Bradycardia", "Monitor heart rate, especially at treatment initiation.", "No specific diet change."),
    ("Benzodiazepine", "Opioid", "Additive CNS and respiratory depression.", "Major", "Respiratory depression, sedation, death", "Avoid combination when possible; use lowest doses for shortest duration if required, with monitoring.", "Avoid alcohol entirely; do not drive or operate machinery."),
    ("Benzodiazepine", "Z-drug hypnotic", "Additive CNS depression.", "Moderate", "Excess sedation, falls, respiratory depression", "Avoid combining; use one sedative-hypnotic at a time.", "Avoid alcohol."),
    ("Benzodiazepine", "Antipsychotic (QT risk)", "Additive sedation; some combinations add QT risk.", "Moderate", "Excess sedation, arrhythmia risk", "Use lowest effective doses; ECG monitoring if risk factors present.", "Avoid alcohol."),
    ("Opioid", "Z-drug hypnotic", "Additive CNS/respiratory depression.", "Major", "Respiratory depression", "Avoid combination; consider non-opioid analgesia.", "Avoid alcohol; do not drive."),
    ("Antipsychotic (QT risk)", "Macrolide antibiotic", "Additive QT interval prolongation.", "Major", "Torsades de pointes risk", "Avoid combination if possible; obtain baseline/follow-up ECG if needed.", "Maintain normal potassium/magnesium intake; avoid excess caffeine."),
    ("Antipsychotic (QT risk)", "Fluoroquinolone", "Additive QT prolongation.", "Major", "Torsades de pointes risk", "Choose non-QT-prolonging antibiotic when possible; ECG monitoring if combined.", "Maintain electrolyte balance (potassium, magnesium)."),
    ("Antipsychotic (QT risk)", "SSRI", "Additive QT prolongation (notably citalopram).", "Moderate", "QT prolongation", "Use lower citalopram dose or alternative SSRI; monitor ECG if risk factors present.", "Maintain electrolyte balance."),
    ("Macrolide antibiotic", "Fluoroquinolone", "Additive QT prolongation from two QT-prolonging classes.", "Moderate", "QT prolongation", "Avoid combining when alternative antibiotics exist.", "Maintain potassium/magnesium intake."),
    ("Antiepileptic (enzyme inducer)", "Levothyroxine", "Enzyme induction increases levothyroxine clearance.", "Moderate", "Hypothyroid symptoms, need for dose increase", "Recheck TSH 6-8 weeks after starting/stopping inducer; adjust dose.", "No specific diet change."),
    ("Antiepileptic (enzyme inducer)", "Corticosteroid", "Enzyme induction increases corticosteroid clearance.", "Moderate", "Reduced steroid efficacy", "May need higher steroid dose; monitor clinical response.", "No specific diet change."),
    ("Antiepileptic (enzyme inducer)", "Immunosuppressant (calcineurin inhibitor)", "Enzyme induction lowers calcineurin inhibitor levels, risking rejection.", "Major", "Transplant rejection risk from subtherapeutic levels", "Monitor trough levels closely; dose adjust proactively.", "No specific diet change."),
    ("Metformin", "Loop diuretic", "Diuretic-induced volume depletion can worsen renal function, raising lactic acidosis risk with metformin.", "Moderate", "Lactic acidosis risk (rare), reduced glycemic control", "Monitor renal function periodically, especially if dehydrated/ill.", "Maintain hydration; limit alcohol."),
    ("Metformin", "Corticosteroid", "Corticosteroids raise blood glucose, opposing metformin's effect.", "Moderate", "Hyperglycemia", "Monitor glucose closely during steroid courses; adjust diabetes regimen as needed.", "Limit added sugars/refined carbohydrates during steroid therapy."),
    ("Sulfonylurea", "Azole antifungal", "CYP2C9 inhibition raises sulfonylurea levels.", "Moderate", "Hypoglycemia", "Monitor blood glucose closely; consider dose reduction.", "Carry fast-acting glucose source; avoid skipping meals."),
    ("Sulfonylurea", "Fluoroquinolone", "Fluoroquinolones can potentiate insulin secretion/action, compounding hypoglycemia risk.", "Moderate", "Hypoglycemia or hyperglycemia (variable)", "Monitor glucose closely during antibiotic course.", "Maintain regular meal timing."),
    ("Insulin", "Beta blocker", "Beta blockers (especially non-selective) can mask hypoglycemia warning symptoms (tremor, tachycardia).", "Moderate", "Masked/prolonged hypoglycemia", "Prefer cardioselective beta blockers; educate patient on sweating as residual warning sign.", "Regular meal timing; monitor glucose more frequently."),
    ("Corticosteroid", "NSAID", "Additive GI mucosal injury risk.", "Moderate", "GI ulceration/bleeding", "Add PPI gastroprotection if combination needed for more than a few days.", "Take with food; avoid alcohol."),
    ("Corticosteroid", "Loop diuretic", "Additive potassium wasting.", "Moderate", "Hypokalemia", "Monitor potassium periodically during co-therapy.", "Include potassium-rich foods (bananas, oranges) unless contraindicated."),
    ("PDE5 inhibitor", "Nitrate", "Both potentiate nitric oxide/cGMP pathway causing profound vasodilation.", "Major", "Severe, life-threatening hypotension", "Contraindicated; do not co-administer under any circumstance within the recommended washout window.", "No diet mitigation - this is a strict drug contraindication."),
    ("PDE5 inhibitor", "Non-dihydropyridine CCB", "Additive vasodilation/hypotension.", "Moderate", "Hypotension, dizziness", "Start PDE5 inhibitor at lowest dose; monitor blood pressure.", "Avoid alcohol which compounds hypotension."),
    ("Proton pump inhibitor", "Levothyroxine", "Reduced gastric acidity impairs levothyroxine tablet dissolution/absorption.", "Moderate", "Reduced levothyroxine efficacy", "Separate dosing by several hours; recheck TSH after starting/stopping PPI.", "Take levothyroxine on an empty stomach, consistently timed relative to PPI."),
    ("Lithium", "Thiazide diuretic", "Reduced renal sodium reabsorption increases lithium reabsorption proximally, raising lithium levels.", "Major", "Lithium toxicity (tremor, confusion, renal injury)", "Avoid combination when possible; if required, reduce lithium dose and monitor levels closely.", "Maintain consistent sodium and fluid intake; dehydration raises lithium levels."),
    ("Lithium", "ACE inhibitor", "Reduced renal lithium clearance via RAAS effects.", "Moderate", "Lithium toxicity", "Monitor lithium levels within 1 week of starting ACE inhibitor.", "Maintain consistent fluid and sodium intake."),
    ("Lithium", "NSAID", "NSAIDs reduce renal prostaglandins, decreasing lithium clearance.", "Moderate", "Lithium toxicity", "Avoid chronic NSAID use; prefer acetaminophen; monitor lithium level if combined.", "Maintain adequate hydration."),
    ("Methotrexate", "NSAID", "NSAIDs reduce renal methotrexate clearance, especially at high (oncologic) doses.", "Major", "Methotrexate toxicity (marrow suppression, mucositis)", "Avoid NSAIDs around high-dose methotrexate administration; caution even at low weekly RA doses.", "Maintain hydration; folic acid supplementation as prescribed."),
    ("Methotrexate", "Proton pump inhibitor", "PPIs may reduce renal tubular methotrexate secretion, raising levels at high doses.", "Moderate", "Methotrexate toxicity", "Consider temporarily holding PPI around high-dose methotrexate cycles.", "Maintain hydration."),
    ("Methotrexate", "Sulfonylurea", "Protein-binding displacement can transiently raise free methotrexate.", "Minor", "Mild increased methotrexate exposure", "Monitor for toxicity signs with combined long-term use.", "No specific diet change."),

    # --- Expansion rules ---
    ("Heparin/LMWH anticoagulant", "Antiplatelet", "Combined anticoagulant and antiplatelet effects.", "Major", "Bleeding", "Reserve for specific indications (e.g. ACS) with close monitoring.", "Avoid alcohol; report unusual bruising/bleeding."),
    ("Heparin/LMWH anticoagulant", "NSAID", "Additive bleeding risk from anticoagulation plus platelet/GI effects.", "Major", "Bleeding", "Avoid NSAIDs where possible; use acetaminophen for pain.", "Avoid alcohol; take any NSAID with food if unavoidable."),
    ("Antiarrhythmic (Class III)", "Macrolide antibiotic", "Additive QT prolongation from two QT-prolonging drugs.", "Major", "Torsades de pointes risk", "Avoid combination; choose non-QT-prolonging antibiotic.", "Maintain potassium/magnesium intake."),
    ("Antiarrhythmic (Class III)", "Statin", "Amiodarone inhibits CYP3A4/CYP2D6, raising statin levels.", "Major", "Myopathy, rhabdomyolysis", "Cap simvastatin dose per label; consider alternative statin.", "Report muscle pain; avoid grapefruit juice."),
    ("Antiarrhythmic (Class III)", "Digoxin", "Amiodarone inhibits P-glycoprotein, raising digoxin levels.", "Major", "Digoxin toxicity", "Reduce digoxin dose by ~50% when starting amiodarone; monitor levels.", "Report nausea, visual disturbance, palpitations."),
    ("Antiarrhythmic (Class III)", "Warfarin/VKA anticoagulant", "Amiodarone inhibits CYP2C9, raising warfarin levels.", "Major", "Increased INR, bleeding", "Reduce warfarin dose ~30-50% when starting amiodarone; monitor INR closely.", "Maintain steady vitamin K intake."),
    ("Theophylline/Xanthine", "Macrolide antibiotic", "CYP1A2/3A4 inhibition raises theophylline levels.", "Major", "Theophylline toxicity (seizures, arrhythmia)", "Monitor theophylline level; reduce dose if combined.", "Limit caffeine intake which compounds stimulant effects."),
    ("Theophylline/Xanthine", "Fluoroquinolone", "CYP1A2 inhibition (notably ciprofloxacin) raises theophylline levels.", "Major", "Theophylline toxicity", "Monitor theophylline level; consider alternative antibiotic.", "Limit caffeine intake."),
    ("Theophylline/Xanthine", "Antitubercular (Rifamycin)", "Enzyme induction lowers theophylline levels.", "Moderate", "Reduced bronchodilator efficacy", "Monitor theophylline level and symptom control; may need dose increase.", "No specific diet change."),
    ("Beta-2 agonist bronchodilator", "Loop diuretic", "Additive hypokalemia from beta-2 stimulation and diuresis.", "Moderate", "Hypokalemia, arrhythmia risk", "Monitor potassium, especially at high bronchodilator doses.", "Include potassium-rich foods unless contraindicated."),
    ("Beta-2 agonist bronchodilator", "Beta blocker", "Pharmacologic antagonism; non-selective beta blockers can blunt bronchodilation and trigger bronchospasm.", "Moderate", "Reduced bronchodilator efficacy, bronchospasm risk", "Prefer cardioselective beta blockers in patients with asthma/COPD.", "No specific diet change."),
    ("H2 receptor antagonist", "Warfarin/VKA anticoagulant", "Cimetidine inhibits CYP metabolism of warfarin, raising INR.", "Moderate", "Increased INR", "Prefer famotidine (minimal interaction) over cimetidine.", "Maintain steady vitamin K intake."),
    ("H2 receptor antagonist", "Theophylline/Xanthine", "Cimetidine inhibits CYP1A2, raising theophylline levels.", "Moderate", "Theophylline toxicity", "Prefer famotidine; monitor theophylline level if cimetidine used.", "Limit caffeine intake."),
    ("Bisphosphonate", "NSAID", "Additive GI mucosal irritation (both can cause esophagitis/ulceration).", "Moderate", "GI irritation, esophagitis", "Avoid lying down after dosing; use lowest effective NSAID dose.", "Take with a full glass of water; avoid lying down for 30-60 minutes."),
    ("Gout agent", "Azole antifungal", "CYP3A4 inhibition raises colchicine levels substantially.", "Major", "Colchicine toxicity (GI, bone marrow suppression)", "Reduce colchicine dose or avoid combination; monitor for toxicity.", "Maintain hydration."),
    ("Gout agent", "Statin", "Additive myopathy risk, particularly colchicine + statin.", "Moderate", "Myopathy risk", "Monitor for muscle pain/weakness; consider dose adjustment.", "Report muscle symptoms promptly."),
    ("Gout agent", "Macrolide antibiotic", "CYP3A4 inhibition raises colchicine levels.", "Major", "Colchicine toxicity", "Avoid combination or reduce colchicine dose substantially.", "Maintain hydration; report GI symptoms."),
    ("HIV protease inhibitor", "Statin", "Strong CYP3A4 inhibition dramatically raises statin levels.", "Major", "Severe myopathy, rhabdomyolysis", "Avoid simvastatin/lovastatin; use low-dose atorvastatin or pravastatin/rosuvastatin.", "Avoid grapefruit juice; report muscle symptoms."),
    ("HIV protease inhibitor", "Benzodiazepine", "CYP3A4 inhibition raises benzodiazepine levels (esp. midazolam/triazolam).", "Major", "Profound sedation, respiratory depression", "Avoid midazolam/triazolam; use lorazepam/oxazepam (non-CYP3A4 dependent).", "Avoid alcohol."),
    ("HIV protease inhibitor", "PDE5 inhibitor", "CYP3A4 inhibition raises PDE5 inhibitor levels.", "Major", "Severe hypotension, priapism risk", "Reduce PDE5 inhibitor dose substantially per label guidance.", "Avoid alcohol; avoid grapefruit juice."),
    ("Antitubercular (Rifamycin)", "Combined oral contraceptive", "Enzyme induction accelerates estrogen/progestin metabolism, reducing contraceptive efficacy.", "Major", "Contraceptive failure, unintended pregnancy", "Use additional/alternative non-hormonal contraception during and after rifamycin therapy.", "No specific diet change."),
    ("Antitubercular (Rifamycin)", "HIV protease inhibitor", "Rifampin induction drastically lowers protease inhibitor levels.", "Major", "Loss of antiretroviral efficacy, resistance risk", "Use rifabutin instead of rifampin in HIV-positive patients on protease inhibitors.", "No specific diet change."),
    ("Chemotherapy - Vinca alkaloid", "Azole antifungal", "CYP3A4 inhibition raises vincristine/vinblastine levels.", "Major", "Severe neurotoxicity", "Avoid combination or reduce chemo dose with close oncology supervision.", "No specific diet change; report numbness/tingling/severe constipation."),
    ("Chemotherapy - Vinca alkaloid", "Macrolide antibiotic", "CYP3A4 inhibition raises vinca alkaloid levels.", "Major", "Severe neurotoxicity, bone marrow suppression", "Avoid combination when possible; oncology team to adjust.", "Report unusual bruising, numbness, infection signs."),
    ("Chemotherapy - Fluoropyrimidine", "Warfarin/VKA anticoagulant", "5-FU/capecitabine inhibit warfarin metabolism, raising INR significantly.", "Major", "Increased INR, bleeding", "Monitor INR very closely during chemotherapy cycles; dose reduce warfarin as needed.", "Maintain steady vitamin K intake; report bleeding."),
    ("Tamoxifen", "SSRI", "Potent CYP2D6-inhibiting SSRIs (paroxetine, fluoxetine) block tamoxifen's conversion to its active metabolite.", "Major", "Reduced tamoxifen efficacy (breast cancer recurrence risk)", "Prefer SSRIs with minimal CYP2D6 inhibition (e.g. sertraline, citalopram) or non-SSRI options.", "No specific diet change."),
    ("First-gen antihistamine", "Benzodiazepine", "Additive CNS depression.", "Moderate", "Excess sedation, falls, impaired coordination", "Avoid combination, especially in elderly patients.", "Avoid alcohol; do not drive."),
    ("First-gen antihistamine", "Opioid", "Additive CNS and respiratory depression.", "Moderate", "Excess sedation, respiratory depression", "Use lowest effective doses; counsel on sedation risk.", "Avoid alcohol."),
    ("Tricyclic antidepressant", "MAOI", "Severe additive serotonergic and noradrenergic toxicity.", "Major", "Serotonin syndrome, hypertensive crisis", "Contraindicated; require washout period when switching.", "Low-tyramine diet required for MAOI component."),
    ("Tricyclic antidepressant", "SSRI", "Additive serotonergic activity plus SSRI inhibition of TCA metabolism (CYP2D6).", "Major", "Serotonin syndrome, TCA toxicity (arrhythmia)", "Avoid combination or use with extreme caution and low TCA doses under specialist care.", "Avoid alcohol; report agitation, tremor, palpitations."),
    ("Tricyclic antidepressant", "Antiarrhythmic (Class III)", "Additive QT prolongation.", "Major", "Torsades de pointes risk", "Avoid combination if possible; ECG monitoring required.", "Maintain potassium/magnesium balance."),
    ("Antiemetic (5-HT3 antagonist)", "SSRI", "Additive serotonergic and QT-prolonging effects.", "Moderate", "Serotonin syndrome risk, QT prolongation", "Use with monitoring; consider alternative antiemetic for long-term use.", "Monitor for agitation, tremor."),
    ("Antiemetic (5-HT3 antagonist)", "Antiarrhythmic (Class III)", "Additive QT prolongation.", "Major", "Torsades de pointes risk", "Avoid combination when possible; ECG monitoring if required.", "Maintain electrolyte balance."),
    ("Muscle relaxant", "Opioid", "Additive CNS/respiratory depression.", "Major", "Respiratory depression, excess sedation", "Avoid combination when possible; use lowest doses with monitoring.", "Avoid alcohol; do not drive."),
    ("Muscle relaxant", "Benzodiazepine", "Additive CNS depression.", "Major", "Excess sedation, respiratory depression, falls", "Avoid combining when possible, especially in elderly patients.", "Avoid alcohol."),
    ("Combined oral contraceptive", "Antiepileptic (enzyme inducer)", "Enzyme induction accelerates hormone metabolism, reducing contraceptive efficacy.", "Major", "Contraceptive failure", "Use additional/alternative non-hormonal contraception.", "No specific diet change."),
    ("Combined oral contraceptive", "Warfarin/VKA anticoagulant", "Estrogen increases clotting factor synthesis, opposing warfarin and raising thrombosis risk independent of INR changes.", "Moderate", "Altered clotting balance, thrombosis risk", "Weigh contraceptive choice carefully in patients on anticoagulation; monitor INR.", "Maintain steady vitamin K intake."),

    # --- Expansion round 2 rules ---
    ("Nasal decongestant", "MAOI", "Decongestant-induced norepinephrine release is potentiated by MAO inhibition.", "Major", "Hypertensive crisis", "Avoid combination entirely; use saline/topical alternatives.", "Low-tyramine diet required for MAOI regardless."),
    ("Nasal decongestant", "Beta blocker", "Unopposed alpha-adrenergic vasoconstriction when beta-effects are blocked.", "Moderate", "Severe hypertension", "Use decongestants cautiously and briefly; monitor blood pressure.", "Limit caffeine/stimulants."),
    ("Antiviral (Herpes)", "NSAID", "Additive nephrotoxic potential, particularly with dehydration.", "Moderate", "Acute kidney injury", "Ensure adequate hydration; monitor renal function with prolonged use.", "Maintain good hydration."),
    ("SGLT2 inhibitor", "Loop diuretic", "Additive volume depletion and hypotension risk.", "Moderate", "Dehydration, hypotension, acute kidney injury", "Monitor volume status and renal function, especially at treatment initiation.", "Maintain adequate hydration; monitor for signs of dehydration."),
    ("SGLT2 inhibitor", "Insulin", "Additive glucose-lowering effect.", "Moderate", "Hypoglycemia", "Consider reducing insulin dose when starting SGLT2 inhibitor; monitor glucose.", "Regular meal timing; carry fast-acting glucose source."),
    ("GLP-1 agonist", "Sulfonylurea", "Additive glucose-lowering effect.", "Moderate", "Hypoglycemia", "Consider reducing sulfonylurea dose when starting GLP-1 agonist.", "Regular meal timing; monitor glucose."),
    ("Antacid", "Fluoroquinolone", "Polyvalent cations chelate fluoroquinolones, blocking absorption.", "Moderate", "Reduced antibiotic efficacy", "Separate dosing by at least 2-6 hours.", "Avoid dairy/calcium-fortified foods near dosing time too."),
    ("Antacid", "Tetracycline", "Polyvalent cations chelate tetracyclines, blocking absorption.", "Moderate", "Reduced antibiotic efficacy", "Separate dosing by at least 2-3 hours.", "Avoid dairy near dosing time."),
    ("Antacid", "Levothyroxine", "Aluminum/magnesium/calcium chelate levothyroxine, reducing absorption.", "Moderate", "Reduced levothyroxine efficacy", "Separate dosing by at least 4 hours.", "Take levothyroxine on an empty stomach, well separated from antacids."),
    ("Iron supplement", "Levothyroxine", "Iron chelates levothyroxine, reducing absorption.", "Moderate", "Reduced levothyroxine efficacy", "Separate dosing by at least 4 hours.", "Take levothyroxine on an empty stomach, separated from iron supplements."),
    ("Iron supplement", "Tetracycline", "Iron chelates tetracyclines, reducing absorption of both.", "Moderate", "Reduced antibiotic and iron efficacy", "Separate dosing by at least 2-3 hours.", "Avoid co-administration at the same meal."),
    ("Iron supplement", "Fluoroquinolone", "Iron chelates fluoroquinolones, reducing absorption.", "Moderate", "Reduced antibiotic efficacy", "Separate dosing by at least 2-6 hours.", "Avoid taking together."),
    ("Anticholinergic (overactive bladder)", "First-gen antihistamine", "Additive anticholinergic burden.", "Moderate", "Confusion, dry mouth, constipation, urinary retention (esp. elderly)", "Avoid combination in elderly patients when possible.", "Maintain hydration and fiber intake to offset constipation."),
    ("Anticholinergic (overactive bladder)", "Tricyclic antidepressant", "Additive anticholinergic burden.", "Moderate", "Confusion, urinary retention, cognitive impairment risk", "Avoid combination in elderly patients when possible.", "Maintain hydration and fiber intake."),
    ("Glaucoma agent (topical beta blocker)", "Beta blocker", "Additive systemic beta-blockade even from topical eye-drop absorption.", "Moderate", "Bradycardia, hypotension", "Monitor heart rate; consider alternative glaucoma therapy if symptomatic.", "No specific diet change."),
    ("Glaucoma agent (topical beta blocker)", "Non-dihydropyridine CCB", "Additive AV nodal suppression.", "Moderate", "Bradycardia, heart block", "Monitor heart rate and conduction; consider alternative agent.", "No specific diet change."),
    ("Antipsychotic (atypical, metabolic risk)", "Corticosteroid", "Additive hyperglycemia risk.", "Moderate", "Hyperglycemia, new-onset diabetes risk", "Monitor blood glucose during co-therapy.", "Limit added sugars/refined carbohydrates."),
    ("Antipsychotic (atypical, metabolic risk)", "Benzodiazepine", "Additive sedation; rare reports of respiratory depression with clozapine specifically.", "Moderate", "Excess sedation", "Use lowest effective doses; monitor respiratory status with clozapine.", "Avoid alcohol."),
    ("Second-gen antihistamine", "Macrolide antibiotic", "CYP3A4 inhibition can raise antihistamine levels (historically significant for older agents; modest for current second-gen agents).", "Minor", "Mild increased antihistamine exposure", "Generally well tolerated; monitor for sedation at higher doses.", "No specific diet change."),
]


# ---- v2 additions: acetaminophen, dairy (food), rifamycin rules ----
CLASSES["Acetaminophen"] = {"drugs": ["Acetaminophen"], "tags": ["hepatic_metabolism", "hepatotoxicity_risk"]}
CLASSES["Calcium / dairy (food)"] = {"drugs": ["Dairy products / calcium-fortified foods"], "tags": ["chelation_risk", "calcium_source"]}
RULES += [
    ("Acetaminophen", "Warfarin/VKA anticoagulant", "Regular acetaminophen use (about 2 g/day or more for several days) can raise INR by interfering with vitamin K-dependent clotting factor synthesis.", "Moderate", "Increased INR, bleeding risk", "Keep acetaminophen at the lowest effective dose and shortest duration; check INR if use becomes regular.", "Avoid alcohol; keep vitamin K intake steady."),
    ("Acetaminophen", "Antiepileptic (enzyme inducer)", "Enzyme induction increases formation of the toxic acetaminophen metabolite, raising hepatotoxicity risk with chronic or high doses.", "Moderate", "Liver injury risk", "Avoid regular high doses; stay within the daily maximum and review liver tests if long-term use is needed.", "Avoid alcohol completely."),
    ("Acetaminophen", "Antitubercular (Rifamycin)", "Additive hepatotoxic potential; rifampin also induces acetaminophen toxic-metabolite formation.", "Moderate", "Liver injury risk", "Limit acetaminophen dose and monitor liver function during rifamycin therapy.", "Avoid alcohol completely."),
    ("Antitubercular (Rifamycin)", "Warfarin/VKA anticoagulant", "Rifampin strongly induces CYP2C9/3A4, accelerating warfarin clearance and lowering INR.", "Major", "Loss of anticoagulation, clot risk", "Monitor INR closely; large warfarin dose increases are often required and must be reduced again after rifampin stops.", "Keep vitamin K intake steady."),
    ("Antitubercular (Rifamycin)", "DOAC anticoagulant", "Rifampin induces P-glycoprotein and CYP3A4, lowering DOAC exposure.", "Major", "Reduced anticoagulant protection", "Avoid the combination; use an alternative anticoagulant under specialist advice.", "No specific diet change."),
    ("Antitubercular (Rifamycin)", "Corticosteroid", "Enzyme induction increases corticosteroid clearance.", "Moderate", "Reduced steroid effect", "A higher steroid dose may be needed; monitor clinical response.", "No specific diet change."),
    ("Antitubercular (Rifamycin)", "Azole antifungal", "Rifampin lowers azole antifungal levels (and azoles can raise rifabutin levels).", "Major", "Antifungal treatment failure", "Avoid or adjust under specialist supervision with drug-level monitoring.", "No specific diet change."),
    ("Antitubercular (Rifamycin)", "Immunosuppressant (calcineurin inhibitor)", "Rifampin induces CYP3A4 and P-glycoprotein, sharply lowering cyclosporine/tacrolimus levels.", "Major", "Transplant rejection risk", "Monitor trough levels closely; substantial dose increases are often required.", "No specific diet change."),
    ("Calcium / dairy (food)", "Tetracycline", "Calcium binds tetracyclines in the gut and blocks absorption.", "Moderate", "Reduced antibiotic effect", "Take the antibiotic at least 2 hours before or 4 hours after dairy or calcium products.", "Separate milk, curd, paneer, cheese and calcium-fortified foods from the dose by 2-4 hours."),
    ("Calcium / dairy (food)", "Fluoroquinolone", "Calcium chelates fluoroquinolones and lowers absorption.", "Moderate", "Reduced antibiotic effect", "Take the antibiotic 2 hours before or 6 hours after calcium-rich meals or supplements.", "Separate dairy and calcium supplements from the dose."),
    ("Calcium / dairy (food)", "Levothyroxine", "Calcium binds levothyroxine and reduces absorption.", "Moderate", "Reduced thyroid hormone effect", "Take levothyroxine on an empty stomach, at least 4 hours apart from calcium products.", "Keep milk, curd and calcium supplements at least 4 hours away from the dose."),
    ("Calcium / dairy (food)", "Bisphosphonate", "Calcium blocks absorption of oral bisphosphonates (absorption is already under 1%).", "Moderate", "Reduced bone-protection effect", "Take with plain water only, 30-60 minutes before food, drink or calcium.", "No dairy, calcium-fortified drinks or supplements for at least 30-60 minutes after the dose."),
]

# Symmetric expansion (rules apply both directions)
rule_lookup = {}
for a, b, mech, sev, effect, mgmt, diet in RULES:
    rule_lookup[(a, b)] = (mech, sev, effect, mgmt, diet)
    rule_lookup[(b, a)] = (mech, sev, effect, mgmt, diet)

SEVERITY_ORDER = {"None": 0, "Minor": 1, "Moderate": 2, "Major": 3}

# ---------------------------------------------------------------------------
# 3. Expand to drug-level pairs
# ---------------------------------------------------------------------------
all_drugs = []
drug_to_class = {}
drug_to_tags = {}
for cls, info in CLASSES.items():
    for d in info["drugs"]:
        all_drugs.append(d)
        drug_to_class[d] = cls
        drug_to_tags[d] = info["tags"]

rows = []
class_list = list(CLASSES.keys())

# Positive (rule-derived) pairs: all drug x drug combos where class pair has a rule
for ca, cb in itertools.combinations_with_replacement(class_list, 2):
    if ca == cb:
        continue
    if (ca, cb) not in rule_lookup:
        continue
    mech, sev, effect, mgmt, diet = rule_lookup[(ca, cb)]
    for da in CLASSES[ca]["drugs"]:
        for db in CLASSES[cb]["drugs"]:
            rows.append({
                "drug_a": da, "drug_b": db,
                "class_a": ca, "class_b": cb,
                "tags_a": ";".join(drug_to_tags[da]), "tags_b": ";".join(drug_to_tags[db]),
                "mechanism": mech, "severity": sev, "effect": effect,
                "management": mgmt, "diet_advice": diet,
            })

positive_pairs = set((r["drug_a"], r["drug_b"]) for r in rows) | set((r["drug_b"], r["drug_a"]) for r in rows)

# Negative pairs: random drug combos with NO authored rule -> label "None"
random.shuffle(all_drugs)
neg_target = int(len(rows) * 0.55)  # keep classes reasonably balanced-ish but not 50/50 (real world: most pairs are benign)
neg_rows = []
attempts = 0
while len(neg_rows) < neg_target and attempts < 200000:
    attempts += 1
    da, db = random.sample(all_drugs, 2)
    if (da, db) in positive_pairs or (db, da) in positive_pairs:
        continue
    ca, cb = drug_to_class[da], drug_to_class[db]
    if ca == cb:
        continue
    neg_rows.append({
        "drug_a": da, "drug_b": db,
        "class_a": ca, "class_b": cb,
        "tags_a": ";".join(drug_to_tags[da]), "tags_b": ";".join(drug_to_tags[db]),
        "mechanism": "No established clinically significant interaction identified.",
        "severity": "None", "effect": "None expected",
        "management": "No special precaution beyond routine monitoring.",
        "diet_advice": "No specific dietary restriction related to this combination.",
    })

# de-duplicate pairs, keep first occurrence
seen, final = set(), []
for r in rows + neg_rows:
    k = tuple(sorted((r["drug_a"], r["drug_b"])))
    if k in seen:
        continue
    seen.add(k)
    final.append(r)

FOOD_CLASSES = {c for c in CLASSES if c.endswith("(food)")}


def export(out_dir):
    import csv, os
    os.makedirs(out_dir, exist_ok=True)
    cols = list(final[0].keys())
    with open(os.path.join(out_dir, "ddi_dataset.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(final)
    drugs = []
    for cls, info in CLASSES.items():
        for d in info["drugs"]:
            drugs.append({"name": d, "class_name": cls, "tags": info["tags"], "kind": "food" if cls in FOOD_CLASSES else "drug"})
    inter = [{"drug_a": r["drug_a"], "drug_b": r["drug_b"], "severity": r["severity"], "mechanism": r["mechanism"],
              "effect": r["effect"], "management": r["management"], "diet_advice": r["diet_advice"]}
             for r in final if r["severity"] != "None"]
    with open(os.path.join(out_dir, "kb_drugs.json"), "w", encoding="utf-8") as f:
        json.dump(drugs, f, indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, "kb_interactions.json"), "w", encoding="utf-8") as f:
        json.dump(inter, f, ensure_ascii=False)
    return len(final), len(drugs), len(inter)


if __name__ == "__main__":
    import os, collections
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    n, nd, ni = export(out)
    print("pairs", n, "| drugs/foods", nd, "| classes", len(CLASSES), "| interaction rows", ni)
    print(collections.Counter(r["severity"] for r in final))
