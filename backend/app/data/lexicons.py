"""Clinical lexicons shared by the NER and the personalised engine."""

# condition_key -> label + surface terms (lower-case). Keys feed the engine's escalation / contraindication rules.
CONDITIONS = {
    "renal_impairment": {"label": "Kidney disease / reduced kidney function", "terms": ["chronic kidney disease", "ckd", "renal failure", "kidney failure", "renal impairment", "renal insufficiency", "kidney disease", "esrd", "dialysis", "nephropathy", "diabetic nephropathy", "renal disease"]},
    "hepatic_impairment": {"label": "Liver disease / reduced liver function", "terms": ["cirrhosis", "liver disease", "hepatic impairment", "hepatitis", "liver failure", "fatty liver", "nafld", "hepatic failure", "liver cirrhosis"]},
    "heart_disease": {"label": "Heart disease / arrhythmia", "terms": ["coronary artery disease", "cad", "myocardial infarction", "atrial fibrillation", "afib", "arrhythmia", "angina", "ischemic heart disease", "ischaemic heart disease", "long qt", "qt prolongation", "heart attack", "prior mi", "cardiomyopathy"]},
    "heart_failure": {"label": "Heart failure", "terms": ["heart failure", "chf", "congestive heart failure", "hfref", "hfpef", "cardiac failure", "lv dysfunction"]},
    "hypertension": {"label": "High blood pressure", "terms": ["hypertension", "htn", "high blood pressure", "elevated blood pressure"]},
    "diabetes": {"label": "Diabetes", "terms": ["diabetes mellitus", "diabetes", "type 2 diabetes", "type 1 diabetes", "t2dm", "t1dm", "dm2", "dm type 2", "niddm", "iddm", "dm"]},
    "asthma_copd": {"label": "Asthma / COPD", "terms": ["asthma", "copd", "chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis", "bronchial asthma"]},
    "seizure_disorder": {"label": "Seizure disorder / epilepsy", "terms": ["epilepsy", "seizure disorder", "seizures", "seizure", "convulsions"]},
    "osteoporosis": {"label": "Osteoporosis", "terms": ["osteoporosis", "osteopenia", "low bone density"]},
    "immunocompromised": {"label": "Weakened immune system", "terms": ["immunocompromised", "immunosuppressed", "hiv", "aids", "organ transplant", "transplant recipient", "chemotherapy", "neutropenia", "kidney transplant", "liver transplant"]},
    "peptic_ulcer_history": {"label": "Stomach ulcer / GI bleeding history", "terms": ["peptic ulcer", "gastric ulcer", "duodenal ulcer", "gi bleed", "gi bleeding", "gastrointestinal bleeding", "upper gi bleed", "melena", "ulcer disease"]},
    "thyroid_disorder": {"label": "Thyroid disorder", "terms": ["hypothyroidism", "hyperthyroidism", "thyroid disease", "graves disease", "hashimoto", "hashimoto's", "thyroiditis", "thyroid disorder"]},
    "obesity": {"label": "Obesity", "terms": ["obesity", "obese", "morbid obesity"]},
    "anemia": {"label": "Anemia", "terms": ["anemia", "anaemia", "iron deficiency anemia", "iron deficiency anaemia", "low hemoglobin"]},
    "glaucoma": {"label": "Glaucoma", "terms": ["glaucoma", "angle closure glaucoma", "open angle glaucoma"]},
    "sleep_apnea": {"label": "Sleep apnea", "terms": ["sleep apnea", "sleep apnoea", "osa", "obstructive sleep apnea"]},
    "pregnancy": {"label": "Pregnancy", "terms": ["pregnant", "pregnancy", "gravid", "expecting"]},
    "elderly": {"label": "Age 65 or older", "terms": []},
}

# allergen_key -> surface terms, and what in the knowledge base it cross-reacts with
ALLERGENS = {
    "nsaid": {"label": "Aspirin / NSAIDs", "terms": ["aspirin", "nsaid", "nsaids", "ibuprofen", "naproxen", "diclofenac", "anti-inflammatory"], "classes": ["NSAID"], "drugs": ["Aspirin"]},
    "sulfa": {"label": "Sulfa (sulfonamide) drugs", "terms": ["sulfa", "sulfonamide", "sulpha", "sulfamethoxazole", "bactrim", "septran"], "classes": ["Sulfonylurea", "Thiazide diuretic"], "drugs": ["Furosemide", "Celecoxib"], "soft": True},
    "opioid": {"label": "Opioids (codeine, morphine)", "terms": ["codeine", "morphine", "opioid", "opioids", "tramadol", "oxycodone"], "classes": ["Opioid"], "drugs": []},
    "statin": {"label": "Statins", "terms": ["statin", "statins"], "classes": ["Statin"], "drugs": []},
    "macrolide": {"label": "Macrolide antibiotics", "terms": ["macrolide", "macrolides", "erythromycin", "azithromycin", "clarithromycin"], "classes": ["Macrolide antibiotic"], "drugs": []},
    "fluoroquinolone": {"label": "Fluoroquinolone antibiotics", "terms": ["fluoroquinolone", "fluoroquinolones", "quinolone", "ciprofloxacin", "levofloxacin"], "classes": ["Fluoroquinolone"], "drugs": []},
    "tetracycline": {"label": "Tetracycline antibiotics", "terms": ["tetracycline", "doxycycline", "minocycline"], "classes": ["Tetracycline"], "drugs": []},
    "ace_inhibitor": {"label": "ACE inhibitors (angioedema / cough)", "terms": ["ace inhibitor", "ace inhibitors", "lisinopril", "enalapril", "ramipril"], "classes": ["ACE inhibitor"], "drugs": []},
    "penicillin": {"label": "Penicillin / amoxicillin", "terms": ["penicillin", "amoxicillin", "ampicillin", "augmentin", "cephalosporin", "cephalosporins"], "classes": [], "drugs": []},
    "latex": {"label": "Latex", "terms": ["latex"], "classes": [], "drugs": []},
    "iodine": {"label": "Iodine / contrast dye", "terms": ["iodine", "contrast dye", "contrast media"], "classes": [], "drugs": []},
    "food": {"label": "Food allergy", "terms": ["peanut", "peanuts", "shellfish", "egg", "eggs", "milk allergy", "soy", "wheat", "tree nuts"], "classes": [], "drugs": []},
}
NO_ALLERGY = ["nkda", "nka", "no known drug allergies", "no known allergies", "no drug allergies", "no allergies"]
