import { useEffect, useState } from "react";
import { Save, UserRound, Ruler, FlaskConical, Phone } from "lucide-react";
import { api } from "../lib/api";
import { Button, Card, CardHeader, Input, Select, Switch, Textarea, PageLoader, useToast } from "./ui";
import { clean, num } from "../lib/utils";

const NUMS = ["height_cm", "weight_kg", "egfr", "serum_creatinine", "alt", "ast", "potassium", "inr", "hba1c", "systolic_bp", "diastolic_bp", "heart_rate"];
const FIELDS = ["full_name", "dob", "sex", "blood_group", "phone", "address", "city", "state", "country", "emergency_contact_name", "emergency_contact_phone", "smoker", "alcohol", "diet_preference", "pregnant", "breastfeeding", "notes", ...NUMS];

/** base = "/patient" (own record) or `/admin/patients/${id}` (doctor editing a patient) */
export default function ProfileForm({ base, onSaved }) {
  const [f, setF] = useState(null);
  const [saving, setSaving] = useState(false);
  const toast = useToast();
  useEffect(() => { api.get(`${base}/profile`).then(setF).catch((e) => toast.error(e.message)); }, [base]); // eslint-disable-line
  if (!f) return <PageLoader />;
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e?.target ? e.target.value : e }));
  const save = async () => {
    setSaving(true);
    try {
      const body = {}; FIELDS.forEach((k) => { body[k] = NUMS.includes(k) ? num(f[k]) : (typeof f[k] === "boolean" ? f[k] : f[k]); });
      const saved = await api.put(`${base}/profile`, clean(body));
      setF(saved); toast.success("Profile saved"); onSaved?.(saved);
    } catch (e) { toast.error(e.message); } finally { setSaving(false); }
  };
  const v = (k) => f[k] ?? "";
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader icon={UserRound} title="Personal details" subtitle={f.age != null ? `${f.age} years old · profile ${f.completeness}% complete` : `Profile ${f.completeness}% complete`} />
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <Input label="Full name" value={v("full_name")} onChange={set("full_name")} autoComplete="name" wrap="sm:col-span-2" />
          <Input label="Date of birth" type="date" value={v("dob")} onChange={set("dob")} max={new Date().toISOString().slice(0, 10)} />
          <Select label="Sex" value={v("sex")} onChange={set("sex")} placeholder="Select" options={[["male", "Male"], ["female", "Female"], ["other", "Other"]]} />
          <Select label="Blood group" value={v("blood_group")} onChange={set("blood_group")} placeholder="Select" options={["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]} />
          <Input label="City" value={v("city")} onChange={set("city")} />
          <Input label="State" value={v("state")} onChange={set("state")} />
          <Input label="Country" value={v("country")} onChange={set("country")} />
        </div>
      </Card>
      <Card>
        <CardHeader icon={Phone} title="Contact" subtitle="Stored encrypted" />
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <Input label="Phone" type="tel" inputMode="tel" value={v("phone")} onChange={set("phone")} autoComplete="tel" />
          <Input label="Address" value={v("address")} onChange={set("address")} autoComplete="street-address" />
          <Input label="Emergency contact name" value={v("emergency_contact_name")} onChange={set("emergency_contact_name")} />
          <Input label="Emergency contact phone" type="tel" inputMode="tel" value={v("emergency_contact_phone")} onChange={set("emergency_contact_phone")} />
        </div>
      </Card>
      <Card>
        <CardHeader icon={Ruler} title="Body & lifestyle" subtitle="These change how risks are scored for you" />
        <div className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-3">
          <Input label="Height (cm)" type="number" inputMode="decimal" value={v("height_cm")} onChange={set("height_cm")} />
          <Input label="Weight (kg)" type="number" inputMode="decimal" value={v("weight_kg")} onChange={set("weight_kg")} hint={f.bmi ? `BMI ${f.bmi}` : undefined} />
          <Select label="Smoking" value={v("smoker")} onChange={set("smoker")} placeholder="Select" options={[["never", "Never"], ["former", "Former smoker"], ["current", "Current smoker"]]} />
          <Select label="Alcohol" value={v("alcohol")} onChange={set("alcohol")} placeholder="Select" options={[["none", "None"], ["occasional", "Occasional"], ["moderate", "Moderate"], ["heavy", "Heavy"]]} />
          <Select label="Diet" value={v("diet_preference")} onChange={set("diet_preference")} placeholder="Select" options={[["vegetarian", "Vegetarian"], ["non_vegetarian", "Non-vegetarian"], ["eggetarian", "Eggetarian"], ["vegan", "Vegan"]]} />
          {f.sex === "female" && <div className="space-y-3 sm:col-span-2 lg:col-span-3"><Switch label="Pregnant" checked={!!f.pregnant} onChange={set("pregnant")} /><Switch label="Breastfeeding" checked={!!f.breastfeeding} onChange={set("breastfeeding")} /></div>}
        </div>
      </Card>
      <Card>
        <CardHeader icon={FlaskConical} title="Recent test results & vitals" subtitle="Optional - from your latest lab report. Reports you upload can fill these in automatically." />
        <div className="grid grid-cols-2 gap-4 p-5 lg:grid-cols-4">
          <Input label="Creatinine (mg/dL)" type="number" step="0.01" inputMode="decimal" value={v("serum_creatinine")} onChange={set("serum_creatinine")} />
          <Input label="eGFR" type="number" inputMode="decimal" value={v("egfr")} onChange={set("egfr")} hint="Estimated from creatinine if empty" />
          <Input label="Potassium (mmol/L)" type="number" step="0.1" inputMode="decimal" value={v("potassium")} onChange={set("potassium")} />
          <Input label="INR" type="number" step="0.1" inputMode="decimal" value={v("inr")} onChange={set("inr")} />
          <Input label="HbA1c (%)" type="number" step="0.1" inputMode="decimal" value={v("hba1c")} onChange={set("hba1c")} />
          <Input label="ALT (U/L)" type="number" inputMode="decimal" value={v("alt")} onChange={set("alt")} />
          <Input label="AST (U/L)" type="number" inputMode="decimal" value={v("ast")} onChange={set("ast")} />
          <Input label="Heart rate (/min)" type="number" inputMode="numeric" value={v("heart_rate")} onChange={set("heart_rate")} />
          <Input label="Systolic BP" type="number" inputMode="numeric" value={v("systolic_bp")} onChange={set("systolic_bp")} />
          <Input label="Diastolic BP" type="number" inputMode="numeric" value={v("diastolic_bp")} onChange={set("diastolic_bp")} />
          <Textarea label="Notes" value={v("notes")} onChange={set("notes")} wrap="col-span-2 lg:col-span-4" hint="Stored encrypted" />
        </div>
      </Card>
      <div className="safe-b sticky bottom-20 z-10 flex justify-end lg:bottom-4"><Button icon={Save} loading={saving} onClick={save} className="w-full shadow-pop sm:w-auto">Save changes</Button></div>
    </div>
  );
}
